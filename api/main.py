"""FastAPI backend for the Lovable frontend.

Run from the project root (the folder containing app.py):

    uvicorn api.main:app --reload --port 8000

The Streamlit app keeps working independently:  streamlit run app.py
"""
import csv
import io
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

# Make `database`, `models`, `utils`, `resume_parser` importable no matter where
# uvicorn is launched from.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.config import CORS_ORIGIN_REGEX, CORS_ORIGINS, JWT_SECRET, USE_FAKE_DB  # noqa: E402

import os  # noqa: E402

if os.environ.get("DB_PORT") and not USE_FAKE_DB:
    # database/db_connection.py has no port setting; hosted MySQL (Railway, Aiven, ...)
    # often isn't on 3306. Inject the port here without editing the database package.
    import mysql.connector as _mysql

    _orig_connect = _mysql.connect
    _db_port = int(os.environ["DB_PORT"])

    def _connect_with_port(*args, **kwargs):
        kwargs.setdefault("port", _db_port)
        return _orig_connect(*args, **kwargs)

    _mysql.connect = _connect_with_port

if USE_FAKE_DB:  # must run before services imports bind create_connection
    from api.dev_fake_db import install_fake_db

    install_fake_db()

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile  # noqa: E402
from fastapi.encoders import jsonable_encoder  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402

from api import services  # noqa: E402
from api.schemas import CareerSelectIn, LoginIn, ProfileIn, RegisterIn  # noqa: E402
from api.security import create_access_token, get_current_user, require_admin  # noqa: E402

log = logging.getLogger("career_api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if JWT_SECRET == "change-me-in-production-please":
        log.warning("JWT_SECRET is not set - using an insecure development default.")
    try:
        services.ensure_tables()
    except Exception as error:  # DB down at boot shouldn't stop the server from starting
        log.warning("Could not verify/create tables at startup: %s", error)
    yield


app = FastAPI(title="Career Readiness API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


# ------------------------------------------------------------------ errors --
def _error(status: int, message: str, **extra):
    return JSONResponse(status_code=status, content={"detail": message, **extra})


@app.exception_handler(services.ValidationFailed)
async def _validation_failed(_req: Request, exc: services.ValidationFailed):
    return _error(exc.status_code, exc.errors[0] if len(exc.errors) == 1 else "; ".join(exc.errors), errors=exc.errors)


@app.exception_handler(services.WorkflowError)
async def _workflow_error(_req: Request, exc: services.WorkflowError):
    return _error(exc.status_code, exc.message, missing_step=exc.missing_step)


@app.exception_handler(RequestValidationError)
async def _request_validation(_req: Request, exc: RequestValidationError):
    errors = []
    for e in exc.errors():
        field = ".".join(str(p) for p in e.get("loc", []) if p != "body")
        errors.append(f"{field}: {e.get('msg')}" if field else e.get("msg"))
    return _error(422, errors[0] if errors else "Invalid request.", errors=errors)


@app.exception_handler(FileNotFoundError)
async def _missing_model(_req: Request, exc: FileNotFoundError):
    return _error(500, str(exc))


@app.exception_handler(RuntimeError)
async def _db_error(_req: Request, exc: RuntimeError):
    # database/*.py wrap every mysql error in RuntimeError
    log.exception("Database error")
    return _error(503, f"Database error: {exc}")


# -------------------------------------------------------------------- misc --
@app.get("/api/health")
def health():
    return {"status": "ok", "fake_db": USE_FAKE_DB}


@app.get("/api/workflow")
def workflow(user=Depends(get_current_user)):
    return services.workflow_status(user["id"])


# -------------------------------------------------------------------- auth --
def _user_public(user):
    return {"id": user["id"], "name": user.get("name"), "email": user.get("email"), "role": user.get("role", "user")}


@app.post("/api/auth/register", status_code=201)
def register(body: RegisterIn):
    confirm = body.confirm_password if body.confirm_password is not None else body.password
    user = services.register(body.name, body.email, body.password, confirm)
    return {
        "message": "Registration successful. You can now log in.",
        "user": _user_public(user),
        "access_token": create_access_token(user),
        "token_type": "bearer",
    }


@app.post("/api/auth/login")
def login(body: LoginIn):
    user = services.authenticate(body.email, body.password)
    return {
        "message": "Login successful.",
        "user": _user_public(user),
        "access_token": create_access_token(user),
        "token_type": "bearer",
    }


@app.get("/api/auth/me")
def me(user=Depends(get_current_user)):
    return {"user": jsonable_encoder(services.clean(_user_public(user)))}


# ----------------------------------------------------------------- profile --
@app.get("/api/profile")
def get_profile(user=Depends(get_current_user)):
    return services.get_profile_view(user)


@app.put("/api/profile")
@app.post("/api/profile")
def save_profile(body: ProfileIn, user=Depends(get_current_user)):
    return services.save_profile(user, body.model_dump())


@app.get("/api/profile/options")
def profile_options():
    return {"interest_options": services.INTEREST_OPTIONS, "career_options": services.CAREER_OPTIONS}


# ------------------------------------------------------------------ resume --
@app.get("/api/resume")
def get_resume(user=Depends(get_current_user)):
    return services.get_resume_view(user["id"])


@app.post("/api/resume")
async def upload_resume(file: UploadFile = File(...), user=Depends(get_current_user)):
    data = await file.read()
    return services.upload_resume(user, file.filename or "", file.content_type, data)


# ------------------------------------------------------------------ career --
@app.get("/api/career")
def get_career(user=Depends(get_current_user)):
    return services.get_career_view(user)


@app.post("/api/career/recommend")
def recommend(user=Depends(get_current_user)):
    return services.generate_recommendation(user)


@app.post("/api/career/select")
def select(body: CareerSelectIn, user=Depends(get_current_user)):
    return services.select_career(user, body.use_ai, body.career)


# --------------------------------------------------------------- skill gap --
@app.get("/api/skill-gap")
def get_skill_gap(user=Depends(get_current_user)):
    return services.get_skill_gap_view(user)


@app.post("/api/skill-gap/run")
def run_skill_gap(user=Depends(get_current_user)):
    return services.run_skill_gap(user)


# ----------------------------------------------------------------- roadmap --
@app.get("/api/roadmap")
def get_roadmap(user=Depends(get_current_user)):
    return services.get_roadmap_view(user)


@app.post("/api/roadmap/generate")
def generate_roadmap(user=Depends(get_current_user)):
    return services.generate_roadmap(user)


# ------------------------------------------------------ dashboard/analytics --
@app.get("/api/dashboard")
def dashboard(user=Depends(get_current_user)):
    return services.get_dashboard(user)


@app.get("/api/analytics")
def analytics(user=Depends(get_current_user)):
    return services.get_analytics(user)


# ------------------------------------------------------------------ report --
@app.get("/api/report/status")
def report_status(user=Depends(get_current_user)):
    return services.report_status(user["id"])


@app.get("/api/report/pdf")
def report_pdf(user=Depends(get_current_user)):
    pdf = services.build_report_pdf(user["id"])
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="career_report_{user["id"]}.pdf"'},
    )


# ------------------------------------------------------------------- admin --
@app.get("/api/admin/overview")
def admin_overview(_admin=Depends(require_admin)):
    return services.get_admin_overview()


@app.get("/api/admin/users")
def admin_users(
    name: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    career_role: Optional[str] = Query(None),
    _admin=Depends(require_admin),
):
    results = services.admin_search(name, email, career_role)
    return {"count": len(results), "results": results}


@app.get("/api/admin/users.csv")
def admin_users_csv(
    name: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    career_role: Optional[str] = Query(None),
    _admin=Depends(require_admin),
):
    results = services.admin_search(name, email, career_role)
    buf = io.StringIO()
    if results:
        writer = csv.DictWriter(buf, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="admin_user_search.csv"'},
    )


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
