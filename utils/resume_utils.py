import os
from pathlib import Path
from typing import List

ALLOWED_RESUME_EXTENSIONS = {"pdf"}
MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024
UPLOAD_FOLDER = os.path.join("uploads", "resumes")


def ensure_resume_upload_dir(base_dir: str = UPLOAD_FOLDER) -> str:
    Path(base_dir).mkdir(parents=True, exist_ok=True)
    return base_dir


def save_uploaded_resume(uploaded_file, target_dir: str = None) -> str:
    target_dir = target_dir or ensure_resume_upload_dir()
    safe_name = os.path.basename(uploaded_file.name).replace(" ", "_")
    target_path = os.path.join(target_dir, safe_name)

    with open(target_path, "wb") as file:
        file.write(uploaded_file.getbuffer())

    return target_path


def calculate_resume_completeness(skills: List[str], projects: List[str], certifications: List[str], education: List[str]) -> int:
    skill_score = min(len(skills), 5) / 5.0 * 40 if skills else 0
    project_score = min(len(projects), 3) / 3.0 * 30 if projects else 0
    certification_score = min(len(certifications), 2) / 2.0 * 20 if certifications else 0
    education_score = min(len(education), 1) / 1.0 * 10 if education else 0
    total_score = skill_score + project_score + certification_score + education_score
    return int(round(min(total_score, 100)))
