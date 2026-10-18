import os
from pathlib import Path

# Project root (the folder that contains app.py, database/, models/, utils/ ...)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Resumes are stored in the same folder the Streamlit app uses (uploads/resumes),
# but resolved as an absolute path so uvicorn can be started from any directory.
RESUME_UPLOAD_DIR = str(PROJECT_ROOT / "uploads" / "resumes")

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production-please")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))  # 24h

# Comma separated list of allowed frontend origins, e.g.
# CORS_ORIGINS="http://localhost:8080,https://my-app.vercel.app"
_default_origins = "http://localhost:8080,http://localhost:5173,http://localhost:3000,http://127.0.0.1:8080,http://127.0.0.1:5173"
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]
# Optional regex (e.g. r"https://.*\.lovable\.app" or r"https://.*\.vercel\.app")
CORS_ORIGIN_REGEX = os.environ.get("CORS_ORIGIN_REGEX") or None

# Set CAREER_API_FAKE_DB=1 to run against an in-memory SQLite shim (demo / tests only).
USE_FAKE_DB = os.environ.get("CAREER_API_FAKE_DB") == "1"
