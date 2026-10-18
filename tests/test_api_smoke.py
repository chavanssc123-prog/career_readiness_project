"""End-to-end smoke test of the FastAPI layer against the in-memory fake DB.

    CAREER_API_FAKE_DB=1 python -m pytest tests/test_api_smoke.py -q

Walks the same order app.py enforces: register -> login -> profile -> resume ->
career -> skill gap -> roadmap -> dashboard/analytics -> PDF, plus admin.
"""
import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["CAREER_API_FAKE_DB"] = "1"
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-32-bytes-long")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from api.main import app  # noqa: E402


def _make_resume_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in [
        "Jane Doe - BTech Computer Science",
        "Skills: Python, SQL, Machine Learning, Excel, Docker, AWS, Linux",
        "",
        "Projects",
        "House price prediction using regression models",
        "Customer churn dashboard built with Power BI",
        "",
        "Certified in Data Science Fundamentals",
    ]:
        c.drawString(72, y, line)
        y -= 18
    c.save()
    return buf.getvalue()


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # keep test uploads out of the real uploads/resumes folder
    from api import services
    services.RESUME_UPLOAD_DIR = str(tmp_path_factory.mktemp("resumes"))
    with TestClient(app) as c:
        yield c


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_full_flow(client):
    assert client.get("/api/health").json()["fake_db"] is True

    # --- protected routes need a token
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard", headers=_auth("garbage")).status_code == 401

    # --- register validation (validate_registration)
    r = client.post("/api/auth/register", json={"name": "", "email": "bad", "password": "short", "confirm_password": "x"})
    assert r.status_code == 400
    assert "Full Name is required." in r.json()["errors"]
    assert "Password must be at least 8 characters long." in r.json()["errors"]

    r = client.post("/api/auth/register", json={
        "name": "Jane Doe", "email": "jane@example.com", "password": "password123", "confirm_password": "password123"})
    assert r.status_code == 201, r.text
    assert r.json()["access_token"]

    r = client.post("/api/auth/register", json={
        "name": "Jane", "email": "jane@example.com", "password": "password123", "confirm_password": "password123"})
    assert r.status_code == 409

    # --- login
    assert client.post("/api/auth/login", json={"email": "", "password": ""}).status_code == 400
    assert client.post("/api/auth/login", json={"email": "jane@example.com", "password": "wrongpass"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "jane@example.com", "password": "password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    h = _auth(token)
    assert client.get("/api/auth/me", headers=h).json()["user"]["email"] == "jane@example.com"

    # --- order of operations: career needs profile first
    r = client.post("/api/career/recommend", headers=h)
    assert r.status_code == 409 and r.json()["missing_step"] == "profile"
    assert client.get("/api/workflow", headers=h).json()["next_step"] == "profile"

    # --- profile
    r = client.get("/api/profile", headers=h)
    assert r.status_code == 200 and r.json()["exists"] is False and r.json()["completion"] == 0

    bad = {"cgpa": 11, "communication": 5, "logical_reasoning": 5, "projects_count": 0,
           "certifications_count": 0, "internship_count": 0, "interest_domain": ""}
    assert client.put("/api/profile", json=bad, headers=h).status_code == 422
    bad.update(cgpa=8, interest_domain="Astrology")
    assert client.put("/api/profile", json=bad, headers=h).status_code == 400

    profile = {"cgpa": 8.4, "communication": 8, "logical_reasoning": 7, "projects_count": 3,
               "certifications_count": 1, "internship_count": 1, "interest_domain": "Data Science"}
    r = client.put("/api/profile", json=profile, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["message"] == "Profile created successfully!"
    assert r.json()["completion"] > 0
    r = client.put("/api/profile", json={**profile, "projects_count": 4}, headers=h)
    assert r.json()["message"] == "Profile updated successfully!"
    assert r.json()["profile"]["projects_count"] == 4

    # --- career needs resume next
    r = client.post("/api/career/recommend", headers=h)
    assert r.status_code == 409 and r.json()["missing_step"] == "resume"

    # --- resume validation + upload
    r = client.post("/api/resume", headers=h, files={"file": ("cv.txt", b"hello", "text/plain")})
    assert r.status_code == 400 and r.json()["detail"] == "Only PDF files are allowed."
    big = b"%PDF" + b"0" * (5 * 1024 * 1024 + 10)
    r = client.post("/api/resume", headers=h, files={"file": ("big.pdf", big, "application/pdf")})
    assert r.status_code == 413

    r = client.post("/api/resume", headers=h, files={"file": ("jane resume.pdf", _make_resume_pdf(), "application/pdf")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["message"] == "Resume uploaded and parsed successfully!"
    assert {"Python", "SQL", "Machine Learning"} <= set(body["skills"])
    assert body["completeness"] > 0
    r = client.post("/api/resume", headers=h, files={"file": ("jane resume.pdf", _make_resume_pdf(), "application/pdf")})
    assert r.json()["message"] == "Resume updated and parsed successfully!"
    assert client.get("/api/resume", headers=h).json()["uploaded"] is True

    # --- skill gap needs a career recommendation
    r = client.post("/api/skill-gap/run", headers=h)
    assert r.status_code == 409 and r.json()["missing_step"] == "career"

    # --- career recommendation (real scikit-learn model)
    r = client.post("/api/career/recommend", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert 1 <= len(body["recommendations"]) <= 5
    top = body["recommendations"][0]["career"]
    assert body["predicted_role"] == top and body["selection_type"] == "AI Recommended"

    g = client.get("/api/career", headers=h).json()
    assert g["recommendations"][0]["career"] == top  # live re-rank matches saved prediction
    r = client.post("/api/career/select", headers=h, json={"use_ai": False, "career": "Astronaut"})
    assert r.status_code == 400
    r = client.post("/api/career/select", headers=h, json={"use_ai": False, "career": "Data Scientist"})
    assert r.status_code == 200 and r.json()["final_selected_role"] == "Data Scientist"
    if top != "Data Scientist":
        assert r.json()["selection_type"] == "User Selected"

    # --- roadmap needs skill gap
    r = client.post("/api/roadmap/generate", headers=h)
    assert r.status_code == 409 and r.json()["missing_step"] == "skill_gap"

    # analytics must not crash in the "Data Scientist, no skill gap yet" state
    assert client.get("/api/analytics", headers=h).status_code == 200

    # --- skill gap
    r = client.post("/api/skill-gap/run", headers=h)
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    assert res["career_role"] == "Data Scientist"
    assert "Python" in res["matched_skills"]
    assert 0 < res["skill_match_score"] <= 100 and 0 < res["readiness_score"] <= 100
    assert set(res["priority"]) == {"High Priority", "Medium Priority", "Low Priority"}
    assert client.get("/api/skill-gap", headers=h).json()["latest_analysis"]["career_role"] == "Data Scientist"

    # --- roadmap
    r = client.get("/api/roadmap", headers=h)
    assert r.status_code == 200 and len(r.json()["timeline"]) == 3 and r.json()["latest_saved"] is None
    r = client.post("/api/roadmap/generate", headers=h)
    assert r.status_code == 200 and r.json()["latest_saved"]["career_role"] == "Data Scientist"

    # --- dashboard / analytics
    d = client.get("/api/dashboard", headers=h).json()
    assert d["selected_career"] == "Data Scientist"
    assert d["workflow"]["report_ready"] is True
    assert len(d["milestones"]) == 3 and len(d["activity"]) == 4
    a = client.get("/api/analytics", headers=h).json()
    assert a["career"]["career_category"] == "Data & Analytics"
    assert a["insights"]

    # --- PDF
    assert client.get("/api/report/status", headers=h).json() == {"ready": True, "missing": []}
    r = client.get("/api/report/pdf", headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"

    # --- admin: forbidden for normal users, allowed for admins
    assert client.get("/api/admin/overview", headers=h).status_code == 403
    r = client.post("/api/auth/login", json={"email": "admin@careerforge.local", "password": "admin12345"})
    ah = _auth(r.json()["access_token"])
    o = client.get("/api/admin/overview", headers=ah)
    assert o.status_code == 200, o.text
    o = o.json()
    assert o["overview"]["total_users"] == 2
    assert o["overview"]["total_career_predictions"] == 1
    assert o["database_health"]["connected"] is True
    s = client.get("/api/admin/users", headers=ah, params={"name": "Jane"}).json()
    assert s["count"] == 1 and s["results"][0]["email"] == "jane@example.com"
    csv = client.get("/api/admin/users.csv", headers=ah, params={"email": "jane"})
    assert csv.status_code == 200 and b"jane@example.com" in csv.content


def test_pdf_blocked_until_complete(client):
    r = client.post("/api/auth/register", json={
        "name": "New User", "email": "new@example.com", "password": "password123", "confirm_password": "password123"})
    h = _auth(r.json()["access_token"])
    s = client.get("/api/report/status", headers=h).json()
    assert s["ready"] is False and "Profile data" in s["missing"]
    assert client.get("/api/report/pdf", headers=h).status_code == 409
    d = client.get("/api/dashboard", headers=h).json()
    assert d["overall_readiness"] == 0 and d["activity"] == []
