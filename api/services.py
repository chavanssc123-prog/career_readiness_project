"""Business logic for each Streamlit page, re-expressed without Streamlit.

Every function here calls the *existing* functions from database/, models/,
utils/ and resume_parser/ in the same order, with the same guards, as the
corresponding page function in app.py. Only UI code (st.markdown, charts, ...)
is left out; values that app.py computed for display are returned as JSON.
"""
from __future__ import annotations

import datetime as _dt
import decimal
import os
from typing import Any, Dict, List, Optional

from database.admin_db import (
    get_career_domain_distribution,
    get_career_override_statistics,
    get_career_recommendation_summary,
    get_career_selection_counts,
    get_database_health,
    get_latest_registered_users,
    get_most_selected_careers,
    get_resume_analytics,
    get_roadmap_analytics,
    get_skill_gap_summary,
    get_system_overview,
    get_user_activity_scores,
)
from database.career_db import (
    create_career_predictions_table_if_missing,
    get_latest_career_prediction,
    save_career_prediction,
    update_latest_career_prediction,
)
from database.db_utils import (
    create_profile,
    create_user,
    get_profile_by_user_id,
    get_user_by_email,
    get_user_by_id,
    update_profile,
)
from database.resume_db import create_resume_data, get_resume_data_by_user, update_resume_data
from database.roadmap_db import create_roadmap_table_if_missing, get_latest_roadmap, save_roadmap
from database.skill_gap_db import (
    create_skill_gap_table_if_missing,
    get_latest_skill_gap_analysis,
    save_skill_gap_analysis,
)
from models.predict import predict_career
from resume_parser.parser import parse_resume
from utils.analytics_utils import (
    build_skill_gap_counts,
    calculate_resume_ats_score,
    compute_overall_readiness,
    generate_analytics_insights,
    infer_career_category,
    normalize_comma_separated_list,
)
from utils.auth import hash_password, verify_password
from utils.career_utils import build_profile_features, build_resume_features
from utils.pdf_report_utils import generate_career_report_pdf
from utils.profile_utils import calculate_profile_completion
from utils.resume_utils import (
    ALLOWED_RESUME_EXTENSIONS,
    MAX_RESUME_SIZE_BYTES,
    calculate_resume_completeness,
    ensure_resume_upload_dir,
    save_uploaded_resume,
)
from utils.roadmap_utils import (
    build_monthly_roadmap,
    build_roadmap_summary,
    get_certification_recommendations,
    get_project_recommendations,
)
from utils.skill_gap_utils import (
    build_current_skills,
    calculate_readiness_score,
    calculate_skill_match_score,
    categorize_skills_by_priority,
    compute_skill_gap,
    format_skill_list,
    get_required_skills_for_career,
)
from utils.validators import validate_registration

from api.config import RESUME_UPLOAD_DIR


# --------------------------------------------------------------------------- #
# Constants copied verbatim from app.py (they live inside page functions there,
# so they cannot be imported without importing Streamlit).
# --------------------------------------------------------------------------- #
INTEREST_OPTIONS = [
    "",
    "Data Science",
    "Artificial Intelligence",
    "Machine Learning",
    "Software Development",
    "Web Development",
    "Cloud Computing",
    "Cyber Security",
    "DevOps",
    "Business Analytics",
]

CAREER_OPTIONS = [
    "Data Analyst",
    "Data Scientist",
    "Machine Learning Engineer",
    "Software Developer",
    "Cloud Engineer",
    "DevOps Engineer",
    "Business Analyst",
    "Cyber Security Analyst",
    "Full Stack Developer",
    "AI Engineer",
]


class WorkflowError(Exception):
    """A prerequisite step is missing (same messages app.py shows with st.error)."""

    def __init__(self, message: str, missing_step: Optional[str] = None, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.missing_step = missing_step
        self.status_code = status_code


class ValidationFailed(Exception):
    def __init__(self, errors: List[str], status_code: int = 400):
        super().__init__("; ".join(errors))
        self.errors = errors
        self.status_code = status_code


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def clean(value: Any) -> Any:
    """Make DB rows JSON friendly (Decimal -> float, datetime -> ISO string)."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k != "password_hash"}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, _dt.datetime):
        # DB datetimes are naive server-local times (datetime.now() / NOW()).
        # Attach the server's UTC offset so browsers in other time zones
        # (e.g. API on Render in UTC, user in IST) show correct "x ago" values.
        return (value.astimezone() if value.tzinfo is None else value).isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    return value


def _selection_type(prediction: Optional[Dict]) -> Optional[str]:
    if not prediction:
        return None
    return "AI Recommended" if prediction.get("selected_role") == prediction.get("predicted_role") else "User Selected"


def _final_role(prediction: Optional[Dict]) -> Optional[str]:
    if not prediction:
        return None
    return prediction.get("selected_role") or prediction.get("recommended_role")


def build_recommendation_reason(career: str, resume_skills: list) -> str:
    """Verbatim copy of app._build_recommendation_reason (UI helper in app.py)."""
    if not resume_skills:
        return "Recommendation based on your profile and resume skills."

    normalized = [skill.strip() for skill in resume_skills if skill]
    key_skills = [skill for skill in normalized if skill.lower() in [
        "aws", "docker", "linux", "kubernetes", "cloud", "python", "sql", "machine learning", "data analysis"
    ]]
    if not key_skills:
        key_skills = normalized[:4]

    reason_skills = ", ".join(key_skills[:4])
    return f"Strong {reason_skills} skills supporting this career recommendation."


def ensure_tables() -> None:
    """app.py calls these at the top of the career / skill-gap / roadmap pages."""
    create_career_predictions_table_if_missing()
    create_skill_gap_table_if_missing()
    create_roadmap_table_if_missing()


def workflow_status(user_id: int) -> Dict[str, Any]:
    profile = get_profile_by_user_id(user_id)
    resume = get_resume_data_by_user(user_id)
    prediction = get_latest_career_prediction(user_id)
    skill_gap = get_latest_skill_gap_analysis(user_id)
    roadmap = get_latest_roadmap(user_id)
    steps = {
        "profile": bool(profile),
        "resume": bool(resume),
        "career": bool(prediction),
        "skill_gap": bool(skill_gap),
        "roadmap": bool(roadmap),
    }
    next_step = next((k for k, done in steps.items() if not done), None)
    return {"steps": steps, "next_step": next_step, "report_ready": all(steps.values())}


# --------------------------------------------------------------------------- #
# Auth (login_page / register_page)
# --------------------------------------------------------------------------- #
def register(name: str, email: str, password: str, confirm_password: str) -> Dict:
    errors = validate_registration(name, email, password, confirm_password)
    if errors:
        raise ValidationFailed(errors)

    if get_user_by_email(email):
        raise ValidationFailed(
            ["That email is already registered. Please log in or use a different email."], status_code=409
        )

    password_hash = hash_password(password)
    user_id = create_user(name, email, password_hash)
    return get_user_by_id(user_id) or {"id": user_id, "name": name, "email": email, "role": "user"}


def authenticate(email: str, password: str) -> Dict:
    if not email or not password:
        raise ValidationFailed(["Please enter both email and password."])

    user = get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise ValidationFailed(["Invalid credentials. Please check your email and password."], status_code=401)
    return user


# --------------------------------------------------------------------------- #
# Profile (profile_page)
# --------------------------------------------------------------------------- #
def _strength(completion: int) -> Dict[str, str]:
    if completion >= 80:
        return {"label": "Strong", "key": "strong"}
    if completion >= 60:
        return {"label": "Good", "key": "good"}
    if completion >= 40:
        return {"label": "Fair", "key": "fair"}
    return {"label": "Needs Work", "key": "needs-work"}


def get_profile_view(user: Dict) -> Dict:
    user_id = user["id"]
    existing_profile = get_profile_by_user_id(user_id)
    completion = calculate_profile_completion(existing_profile)

    next_steps: List[str] = []
    if existing_profile and completion < 100:
        if not existing_profile.get("interest_domain"):
            next_steps.append("Select your primary interest domain")
        if (existing_profile.get("projects_count") or 0) < 3:
            next_steps.append("Add more projects to your profile")
        if (existing_profile.get("internship_count") or 0) < 1:
            next_steps.append("Add internship experience if available")
        if (existing_profile.get("certifications_count") or 0) < 2:
            next_steps.append("Consider adding professional certifications")

    p = existing_profile or {}
    checklist = {
        "personal_info": float(p.get("cgpa") or 0) > 0,
        "academic_details": float(p.get("cgpa") or 0) > 0,
        "career_interest": bool(p.get("interest_domain")),
        "projects": int(p.get("projects_count") or 0) >= 1,
        "certifications": int(p.get("certifications_count") or 0) >= 1,
    }

    return clean({
        "user": {"id": user["id"], "name": user.get("name"), "email": user.get("email"), "role": user.get("role", "user")},
        "profile": existing_profile,
        "exists": bool(existing_profile),
        "completion": completion,
        "strength": _strength(completion),
        "status": "AI-Verified Profile" if existing_profile else "Profile Pending",
        "checklist": checklist,
        "next_steps": next_steps,
        "interest_options": INTEREST_OPTIONS,
    })


def save_profile(user: Dict, data: Dict) -> Dict:
    if data["interest_domain"] not in INTEREST_OPTIONS:
        raise ValidationFailed([f"Interest domain must be one of: {', '.join(o for o in INTEREST_OPTIONS if o)}"])

    user_id = user["id"]
    existing_profile = get_profile_by_user_id(user_id)
    args = (
        user_id,
        data["cgpa"],
        data["communication"],
        data["logical_reasoning"],
        data["projects_count"],
        data["certifications_count"],
        data["internship_count"],
        data["interest_domain"],
    )
    if existing_profile:
        update_profile(*args)
        message = "Profile updated successfully!"
    else:
        create_profile(*args)
        message = "Profile created successfully!"

    view = get_profile_view(user)
    view["message"] = message
    return view


# --------------------------------------------------------------------------- #
# Resume (resume_upload_page)
# --------------------------------------------------------------------------- #
class _UploadedFileAdapter:
    """Gives FastAPI upload bytes the `.name` / `.getbuffer()` interface that
    utils.resume_utils.save_uploaded_resume expects from a Streamlit UploadedFile."""

    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getbuffer(self):
        return memoryview(self._data)


def _split(value: Optional[str]) -> List[str]:
    # Same split app.py uses when reading stored resume data back.
    return value.split(", ") if value else []


def get_resume_view(user_id: int, parsed_data: Optional[Dict] = None) -> Dict:
    resume_data = get_resume_data_by_user(user_id)
    current: Dict[str, List[str]] = {}
    if parsed_data:
        current = parsed_data
    elif resume_data:
        current = {
            "skills": _split(resume_data.get("skills")),
            "certifications": _split(resume_data.get("certifications")),
            "education": _split(resume_data.get("education")),
            "projects": _split(resume_data.get("projects")),
        }

    completeness = 0
    if current:
        completeness = calculate_resume_completeness(
            current.get("skills", []),
            current.get("projects", []),
            current.get("certifications", []),
            current.get("education", []),
        )

    if completeness >= 80:
        badge, advice = "Ready", "Excellent resume! Your analysis is in a strong position."
    elif completeness >= 60:
        badge, advice = "Improving", "Good resume. Add a few more details for a stronger score."
    else:
        badge, advice = "Needs Work", "Your resume could benefit from more information and detail."

    file_path = resume_data.get("resume_file") if resume_data else None
    return clean({
        "uploaded": bool(resume_data),
        "resume": resume_data,
        "file_name": os.path.basename(file_path) if file_path else None,
        "upload_date": resume_data.get("upload_date") if resume_data else None,
        "skills": [s.strip() for s in current.get("skills", []) if s and s.strip()],
        "projects": [s.strip() for s in current.get("projects", []) if s and s.strip()],
        "certifications": [s.strip() for s in current.get("certifications", []) if s and s.strip()],
        "education": [s.strip() for s in current.get("education", []) if s and s.strip()],
        "completeness": completeness,
        "ats_score": calculate_resume_ats_score(resume_data) if resume_data else 0.0,
        "status_badge": badge if current else None,
        "advice": advice if current else None,
        "max_size_bytes": MAX_RESUME_SIZE_BYTES,
    })


def upload_resume(user: Dict, filename: str, content_type: Optional[str], data: bytes) -> Dict:
    # Same three validations as app.py, in the same order.
    if content_type != "application/pdf":
        raise ValidationFailed(["Only PDF files are allowed."])
    if len(data) > MAX_RESUME_SIZE_BYTES:
        raise ValidationFailed([
            f"The uploaded resume exceeds the maximum allowed size of 5 MB. Your file: {len(data) / (1024 * 1024):.2f} MB"
        ], status_code=413)
    if (filename or "").split(".")[-1].lower() not in ALLOWED_RESUME_EXTENSIONS:
        raise ValidationFailed(["Invalid file extension. Only .pdf resumes are accepted."])

    user_id = user["id"]
    ensure_resume_upload_dir(RESUME_UPLOAD_DIR)
    resume_data = get_resume_data_by_user(user_id)

    # Prefix with the user id so two users uploading "resume.pdf" don't overwrite
    # each other's file (the Streamlit flow saves under the raw file name).
    adapter = _UploadedFileAdapter(f"{user_id}_{os.path.basename(filename)}", data)
    saved_path = save_uploaded_resume(adapter, RESUME_UPLOAD_DIR)
    try:
        parsed_data = parse_resume(saved_path)
    except Exception as error:  # app.py: st.error(f"Unable to parse resume: {error}")
        raise ValidationFailed([f"Unable to parse resume: {error}"], status_code=422)

    skills_text = ", ".join(parsed_data.get("skills", []))
    projects_text = ", ".join(parsed_data.get("projects", []))
    certifications_text = ", ".join(parsed_data.get("certifications", []))
    education_text = ", ".join(parsed_data.get("education", []))

    if resume_data:
        update_resume_data(user_id, saved_path, skills_text, projects_text, certifications_text, education_text)
        message = "Resume updated and parsed successfully!"
    else:
        create_resume_data(user_id, saved_path, skills_text, projects_text, certifications_text, education_text)
        message = "Resume uploaded and parsed successfully!"

    view = get_resume_view(user_id, parsed_data)
    view["message"] = message
    return view


# --------------------------------------------------------------------------- #
# Career recommendation (career_recommendation_page)
# --------------------------------------------------------------------------- #
def _career_prereqs(user_id: int):
    create_career_predictions_table_if_missing()
    profile = get_profile_by_user_id(user_id)
    resume_data_db = get_resume_data_by_user(user_id)
    if not profile:
        raise WorkflowError("Profile data is required to generate a recommendation.", "profile")
    if not resume_data_db:
        raise WorkflowError("Resume data is required to generate a recommendation.", "resume")
    return profile, resume_data_db


def _career_state(user_id: int, resume_data_db: Optional[Dict], recommendations: Optional[List[Dict]] = None) -> Dict:
    latest_prediction = get_latest_career_prediction(user_id)
    state: Dict[str, Any] = {
        "career_options": CAREER_OPTIONS,
        "latest_prediction": latest_prediction,
        "recommendations": recommendations,
        "predicted_role": None,
        "prediction_confidence": None,
        "selected_role": None,
        "final_selected_role": None,
        "selection_type": None,
        "reason": None,
        "career_category": None,
    }
    if latest_prediction:
        predicted = latest_prediction.get("predicted_role") or latest_prediction.get("recommended_role")
        selected = latest_prediction.get("selected_role") or predicted
        state.update({
            "predicted_role": predicted,
            "prediction_confidence": float(
                latest_prediction.get("prediction_confidence") or latest_prediction.get("confidence_score") or 0.0
            ),
            "selected_role": selected,
            "final_selected_role": selected,
            "selection_type": "AI Recommended" if selected == predicted else "User Selected",
            "career_category": infer_career_category(selected),
        })
        if resume_data_db:
            state["reason"] = build_recommendation_reason(predicted, _split(resume_data_db.get("skills")))
    return clean(state)


def _rank(recommendations: List[Dict]) -> List[Dict]:
    ranked = []
    for idx, rec in enumerate(recommendations[:5], 1):
        confidence = rec["confidence"]
        if confidence >= 80:
            match = "Excellent Match"
        elif confidence >= 60:
            match = "Good Match"
        else:
            match = "Potential Match"
        ranked.append({"rank": idx, "career": rec["career"], "confidence": round(float(confidence), 2), "match_label": match})
    return ranked


def model_career_labels() -> List[str]:
    from models.predict import _load_label_encoder

    try:
        return [str(c) for c in _load_label_encoder().classes_]
    except Exception:
        return []


def get_career_view(user: Dict) -> Dict:
    profile, resume_data_db = _career_prereqs(user["id"])
    recommendations = None
    if get_latest_career_prediction(user["id"]):
        # Re-run the same model (read-only, nothing saved) so the page can list the
        # ranked options again after a reload. Only POST /career/recommend saves.
        try:
            recommendations = _rank(predict_career(build_profile_features(profile), build_resume_features(resume_data_db)))
        except Exception:
            recommendations = None
    return _career_state(user["id"], resume_data_db, recommendations)


def generate_recommendation(user: Dict) -> Dict:
    user_id = user["id"]
    profile, resume_data_db = _career_prereqs(user_id)
    profile_features = build_profile_features(profile)
    resume_features = build_resume_features(resume_data_db)

    recommendations = predict_career(profile_features, resume_features)
    if not recommendations:
        raise WorkflowError("No recommendation results available.", None, status_code=422)

    ranked = _rank(recommendations)

    top_career = recommendations[0]
    save_career_prediction(user_id, top_career["career"], round(top_career["confidence"], 2), top_career["career"])
    return _career_state(user_id, resume_data_db, ranked)


def select_career(user: Dict, use_ai: bool, career: Optional[str]) -> Dict:
    user_id = user["id"]
    profile, resume_data_db = _career_prereqs(user_id)
    latest = get_latest_career_prediction(user_id)
    if not latest:
        raise WorkflowError("Generate an AI recommendation before selecting a career.", "career")

    predicted = latest.get("predicted_role") or latest.get("recommended_role")
    if use_ai:
        role = predicted
    else:
        # Streamlit's dropdown offers CAREER_OPTIONS; the Lovable UI also lets the user
        # pick one of the model's other ranked recommendations, so accept model labels too.
        allowed = list(dict.fromkeys(CAREER_OPTIONS + model_career_labels()))
        if not career or career not in allowed:
            raise ValidationFailed([f"Career must be one of: {', '.join(allowed)}"])
        role = career

    update_latest_career_prediction(user_id, role)
    state = _career_state(user_id, resume_data_db)
    state["message"] = (
        "AI recommended career confirmed as final selection!" if use_ai else f"Final career path set to {role}!"
    )
    return state


# --------------------------------------------------------------------------- #
# Skill gap (skill_gap_analysis_page)
# --------------------------------------------------------------------------- #
def _skill_gap_prereqs(user_id: int):
    create_skill_gap_table_if_missing()
    profile = get_profile_by_user_id(user_id)
    resume_data_db = get_resume_data_by_user(user_id)
    latest_prediction = get_latest_career_prediction(user_id)
    if not profile:
        raise WorkflowError("Profile data is required to perform a skill gap analysis.", "profile")
    if not resume_data_db:
        raise WorkflowError("Resume data is required to perform a skill gap analysis.", "resume")
    if not latest_prediction:
        raise WorkflowError("A career recommendation is required before running skill gap analysis.", "career")
    return profile, resume_data_db, latest_prediction


def _format_stored_gap(analysis: Optional[Dict]) -> Optional[Dict]:
    if not analysis:
        return None
    matched = normalize_comma_separated_list(analysis.get("matched_skills"))
    missing = normalize_comma_separated_list(analysis.get("missing_skills"))
    extra = normalize_comma_separated_list(analysis.get("extra_skills"))
    return clean({
        **analysis,
        "career_role": analysis.get("career_role"),
        "required_skills": format_skill_list(get_required_skills_for_career(analysis.get("career_role"))),
        "matched_skills": format_skill_list(matched),
        "missing_skills": format_skill_list(missing),
        "extra_skills": format_skill_list(extra),
        "priority": {k: format_skill_list(v) for k, v in categorize_skills_by_priority(missing).items()},
        "counts": build_skill_gap_counts(analysis),
    })


def get_skill_gap_view(user: Dict) -> Dict:
    profile, resume_data_db, latest_prediction = _skill_gap_prereqs(user["id"])
    previous = get_latest_skill_gap_analysis(user["id"])
    return clean({
        "current_recommendation": {
            "recommended_role": latest_prediction.get("recommended_role"),
            "confidence_score": latest_prediction.get("confidence_score"),
            "final_career_role": _final_role(latest_prediction),
            "selection_type": _selection_type(latest_prediction),
        },
        "latest_analysis": _format_stored_gap(previous),
    })


def run_skill_gap(user: Dict) -> Dict:
    user_id = user["id"]
    profile, resume_data_db, latest_prediction = _skill_gap_prereqs(user_id)

    profile_features = build_profile_features(profile)
    resume_features = build_resume_features(resume_data_db)
    current_skills = build_current_skills(profile_features, resume_features)
    final_career_role = latest_prediction.get("selected_role") or latest_prediction.get("recommended_role")
    required_skills = get_required_skills_for_career(final_career_role)
    matched_skills, missing_skills, extra_skills = compute_skill_gap(final_career_role, current_skills)
    skill_match_score = calculate_skill_match_score(matched_skills, required_skills)
    readiness_score = calculate_readiness_score(skill_match_score, profile_features)
    priority_categories = categorize_skills_by_priority(missing_skills)

    save_skill_gap_analysis(
        user_id, final_career_role, matched_skills, missing_skills, extra_skills, skill_match_score, readiness_score
    )

    view = get_skill_gap_view(user)
    view["result"] = clean({
        "career_role": final_career_role,
        "required_skills": format_skill_list(required_skills),
        "matched_skills": format_skill_list(matched_skills),
        "missing_skills": format_skill_list(missing_skills),
        "extra_skills": format_skill_list(extra_skills),
        "skill_match_score": skill_match_score,
        "readiness_score": readiness_score,
        "priority": {k: format_skill_list(v) for k, v in priority_categories.items()},
        "counts": {"Matched": len(matched_skills), "Missing": len(missing_skills), "Extra": len(extra_skills)},
        "role_has_requirements": bool(required_skills),
    })
    return view


# --------------------------------------------------------------------------- #
# Roadmap (roadmap_generator_page)
# --------------------------------------------------------------------------- #
def _roadmap_context(user_id: int) -> Dict:
    create_roadmap_table_if_missing()
    create_skill_gap_table_if_missing()
    profile = get_profile_by_user_id(user_id)
    resume_data_db = get_resume_data_by_user(user_id)
    latest_prediction = get_latest_career_prediction(user_id)
    latest_skill_gap = get_latest_skill_gap_analysis(user_id)

    if not profile:
        raise WorkflowError("Profile data is required to generate a roadmap.", "profile")
    if not resume_data_db:
        raise WorkflowError("Resume data is required to generate a roadmap.", "resume")
    if not latest_prediction:
        raise WorkflowError("A career recommendation is required before generating a roadmap.", "career")
    if not latest_skill_gap:
        raise WorkflowError("A skill gap analysis is required before generating a roadmap.", "skill_gap")

    final_career_role = latest_prediction.get("selected_role") or latest_prediction.get("recommended_role")
    readiness_score = float(latest_skill_gap["readiness_score"] or 0.0)
    missing_skills = (
        [skill.strip() for skill in latest_skill_gap["missing_skills"].split(",") if skill.strip()]
        if latest_skill_gap.get("missing_skills") else []
    )
    project_recommendations = get_project_recommendations(final_career_role)
    certification_recommendations = get_certification_recommendations(final_career_role)
    monthly_map = build_monthly_roadmap(final_career_role, missing_skills, readiness_score)
    roadmap_text = build_roadmap_summary(final_career_role, monthly_map, project_recommendations, certification_recommendations)
    return {
        "final_career_role": final_career_role,
        "readiness_score": readiness_score,
        "missing_skills": missing_skills,
        "selection_type": _selection_type(latest_prediction),
        "projects": project_recommendations,
        "certifications": certification_recommendations,
        "monthly_map": monthly_map,
        "roadmap_text": roadmap_text,
        "duration_months": len(monthly_map),
    }


def get_roadmap_view(user: Dict) -> Dict:
    ctx = _roadmap_context(user["id"])
    previous_roadmap = get_latest_roadmap(user["id"])
    return clean({
        "final_career_role": ctx["final_career_role"],
        "readiness_score": ctx["readiness_score"],
        "missing_skills": format_skill_list(ctx["missing_skills"]),
        "selection_type": ctx["selection_type"],
        "timeline": [{"month": m, "goals": g} for m, g in ctx["monthly_map"].items()],
        "projects": ctx["projects"],
        "certifications": ctx["certifications"],
        "duration_months": ctx["duration_months"],
        "roadmap_text": ctx["roadmap_text"],
        "latest_saved": previous_roadmap,
    })


def generate_roadmap(user: Dict) -> Dict:
    ctx = _roadmap_context(user["id"])
    save_roadmap(user["id"], ctx["final_career_role"], ctx["roadmap_text"], ctx["duration_months"], ctx["readiness_score"])
    view = get_roadmap_view(user)
    view["message"] = "Personalized roadmap saved successfully."
    return view


# --------------------------------------------------------------------------- #
# Dashboard (dashboard_page) and Analytics (analytics_dashboard_page)
# --------------------------------------------------------------------------- #
def _collect(user_id: int) -> Dict:
    profile = get_profile_by_user_id(user_id)
    resume_data = get_resume_data_by_user(user_id)
    latest_prediction = get_latest_career_prediction(user_id)
    latest_skill_gap = get_latest_skill_gap_analysis(user_id)
    latest_roadmap = get_latest_roadmap(user_id)

    profile_completion = calculate_profile_completion(profile)
    ats_score = calculate_resume_ats_score(resume_data) if resume_data else 0.0
    skill_match_score = float(latest_skill_gap.get("skill_match_score") or 0.0) if latest_skill_gap else 0.0
    roadmap_progress = float(latest_roadmap.get("readiness_score") or 0.0) if latest_roadmap else 0.0
    overall_readiness = compute_overall_readiness(profile_completion, ats_score, skill_match_score, roadmap_progress)
    return {
        "profile": profile,
        "resume_data": resume_data,
        "latest_prediction": latest_prediction,
        "latest_skill_gap": latest_skill_gap,
        "latest_roadmap": latest_roadmap,
        "profile_completion": profile_completion,
        "ats_score": ats_score,
        "skill_match_score": skill_match_score,
        "roadmap_progress": roadmap_progress,
        "overall_readiness": overall_readiness,
    }


def _activity_feed(d: Dict) -> List[Dict]:
    """Real activity items built from stored timestamps (the Streamlit dashboard
    shows a hard-coded list here)."""
    items = []
    p = d["latest_prediction"]
    if p:
        items.append({
            "type": "career",
            "title": "New AI recommendation",
            "description": f"{p.get('recommended_role')} · {float(p.get('confidence_score') or 0):.0f}%",
            "timestamp": p.get("prediction_date"),
        })
    r = d["resume_data"]
    if r:
        items.append({
            "type": "resume",
            "title": "Resume analyzed",
            "description": f"ATS score {d['ats_score']:.0f}",
            "timestamp": r.get("upload_date"),
        })
    g = d["latest_skill_gap"]
    if g:
        items.append({
            "type": "skill_gap",
            "title": "Skill gap analysis",
            "description": f"{float(g.get('skill_match_score') or 0):.0f}% match for {g.get('career_role')}",
            "timestamp": g.get("created_at"),
        })
    rm = d["latest_roadmap"]
    if rm:
        items.append({
            "type": "roadmap",
            "title": "Roadmap generated",
            "description": f"{rm.get('duration_months')}-month plan · {rm.get('career_role')}",
            "timestamp": rm.get("created_at"),
        })
    items.sort(key=lambda i: str(i["timestamp"] or ""), reverse=True)
    return items


def get_dashboard(user: Dict) -> Dict:
    user_id = user["id"]
    d = _collect(user_id)
    gap = d["latest_skill_gap"]
    matched = normalize_comma_separated_list(gap.get("matched_skills")) if gap else []
    missing = normalize_comma_separated_list(gap.get("missing_skills")) if gap else []
    extra = normalize_comma_separated_list(gap.get("extra_skills")) if gap else []
    selected_career = _final_role(d["latest_prediction"])

    milestones = []
    roadmap = d["latest_roadmap"]
    if roadmap and d["latest_skill_gap"]:
        # Rebuild the month-by-month goals for the saved role with the same util.
        monthly = build_monthly_roadmap(
            roadmap.get("career_role"),
            missing,
            float(roadmap.get("readiness_score") or 0.0),
        )
        for idx, (month, goals) in enumerate(monthly.items(), 1):
            milestones.append({"month": f"M{idx}", "label": month, "title": goals[0] if goals else month, "goals": goals})

    return clean({
        "user": {"id": user["id"], "name": user.get("name"), "email": user.get("email"), "role": user.get("role", "user")},
        "profile_completion": d["profile_completion"],
        "ats_score": d["ats_score"],
        "skill_match_score": d["skill_match_score"],
        "roadmap_progress": d["roadmap_progress"],
        "overall_readiness": d["overall_readiness"],
        "points_away": 100 - int(d["overall_readiness"]),
        "selected_career": selected_career,
        "career_confidence": float(d["latest_prediction"].get("confidence_score") or 0) if d["latest_prediction"] else None,
        "selection_type": _selection_type(d["latest_prediction"]),
        "skill_counts": {"matched": len(matched), "missing": len(missing), "extra": len(extra)},
        "missing_skills": format_skill_list(missing),
        "matched_skills": format_skill_list(matched),
        "roadmap": {
            "career_role": roadmap.get("career_role"),
            "duration_months": roadmap.get("duration_months"),
            "readiness_score": roadmap.get("readiness_score"),
            "created_at": roadmap.get("created_at"),
        } if roadmap else None,
        "milestones": milestones,
        "activity": _activity_feed(d),
        "workflow": workflow_status(user_id),
    })


def get_analytics(user: Dict) -> Dict:
    user_id = user["id"]
    d = _collect(user_id)
    profile, resume_data = d["profile"], d["resume_data"]
    latest_prediction, latest_skill_gap, latest_roadmap = d["latest_prediction"], d["latest_skill_gap"], d["latest_roadmap"]

    selected_career = _final_role(latest_prediction)
    career_category = infer_career_category(selected_career)
    # NOTE: generate_analytics_insights() crashes (None.get) when a "Data Scientist"
    # prediction exists but no skill-gap row yet. `{}` is falsy exactly like None in
    # every other branch of that function, so passing it keeps results identical
    # and only prevents the crash.
    insights = generate_analytics_insights(
        profile, resume_data, latest_prediction, latest_skill_gap or {}, latest_roadmap,
        d["profile_completion"], d["ats_score"], d["skill_match_score"], d["roadmap_progress"],
    )

    skills = normalize_comma_separated_list(resume_data.get("skills")) if resume_data else []
    projects = normalize_comma_separated_list(resume_data.get("projects")) if resume_data else []
    certifications = normalize_comma_separated_list(resume_data.get("certifications")) if resume_data else []
    education = normalize_comma_separated_list(resume_data.get("education")) if resume_data else []

    return clean({
        "summary": {
            "profile_completion": d["profile_completion"],
            "ats_score": d["ats_score"],
            "skill_match_score": d["skill_match_score"],
            "roadmap_progress": d["roadmap_progress"],
            "overall_readiness": d["overall_readiness"],
        },
        "profile": {
            "exists": bool(profile),
            "cgpa": profile.get("cgpa") if profile else None,
            "projects_count": profile.get("projects_count", 0) if profile else 0,
            "internship_count": profile.get("internship_count", 0) if profile else 0,
            "certifications_count": profile.get("certifications_count", 0) if profile else 0,
            "interest_domain": profile.get("interest_domain") if profile else None,
        },
        "resume": {
            "uploaded": bool(resume_data),
            "ats_score": d["ats_score"],
            "skills_count": len(skills),
            "projects_count": len(projects),
            "certifications_count": len(certifications),
            "education_count": len(education),
            "skills": skills,
        },
        "career": {
            "final_selected_career": selected_career,
            "confidence": latest_prediction.get("confidence_score") if latest_prediction else None,
            "career_category": career_category,
            "prediction_date": latest_prediction.get("prediction_date") if latest_prediction else None,
            "selection_type": _selection_type(latest_prediction),
        } if latest_prediction else None,
        "skill_gap": {
            "counts": build_skill_gap_counts(latest_skill_gap),
            "matched_skills": format_skill_list(normalize_comma_separated_list(latest_skill_gap.get("matched_skills"))),
            "missing_skills": format_skill_list(normalize_comma_separated_list(latest_skill_gap.get("missing_skills"))),
            "extra_skills": format_skill_list(normalize_comma_separated_list(latest_skill_gap.get("extra_skills"))),
            "priority": {
                k: format_skill_list(v)
                for k, v in categorize_skills_by_priority(
                    normalize_comma_separated_list(latest_skill_gap.get("missing_skills"))
                ).items()
            },
            "skill_match_score": d["skill_match_score"],
            "readiness_score": latest_skill_gap.get("readiness_score"),
        } if latest_skill_gap else {"counts": build_skill_gap_counts(None)},
        "roadmap": {
            "career_role": latest_roadmap.get("career_role"),
            "duration_months": latest_roadmap.get("duration_months"),
            "readiness_score": latest_roadmap.get("readiness_score"),
            "roadmap_text": latest_roadmap.get("roadmap_text"),
            "projects": get_project_recommendations(latest_roadmap.get("career_role", "")),
            "certifications": get_certification_recommendations(latest_roadmap.get("career_role", "")),
        } if latest_roadmap else None,
        "insights": insights,
    })


# --------------------------------------------------------------------------- #
# PDF report (pdf_career_report_page)
# --------------------------------------------------------------------------- #
def report_status(user_id: int) -> Dict:
    missing = []
    if not get_profile_by_user_id(user_id):
        missing.append("Profile data")
    if not get_resume_data_by_user(user_id):
        missing.append("Resume data")
    if not get_latest_career_prediction(user_id):
        missing.append("Career recommendation")
    if not get_latest_skill_gap_analysis(user_id):
        missing.append("Skill gap analysis")
    if not get_latest_roadmap(user_id):
        missing.append("Personalized roadmap")
    return {"ready": not missing, "missing": missing}


def build_report_pdf(user_id: int) -> bytes:
    user = get_user_by_id(user_id)
    profile = get_profile_by_user_id(user_id)
    resume_data = get_resume_data_by_user(user_id)
    career_prediction = get_latest_career_prediction(user_id)
    skill_gap = get_latest_skill_gap_analysis(user_id)
    roadmap = get_latest_roadmap(user_id)

    status = report_status(user_id)
    if status["missing"]:
        raise WorkflowError(
            "Cannot generate report until all sections are complete. Missing: " + ", ".join(status["missing"]),
            None,
        )

    ats_score = calculate_resume_ats_score(resume_data)
    selected_career = career_prediction.get("selected_role") or career_prediction.get("recommended_role")
    career_category = infer_career_category(selected_career)
    overall_readiness = compute_overall_readiness(
        calculate_profile_completion(profile),
        ats_score,
        float(skill_gap.get("skill_match_score", 0.0) or 0.0),
        float(roadmap.get("readiness_score", 0.0) or 0.0),
    )
    analytics_summary = {
        "career_category": career_category,
        "ats_score": ats_score,
        "profile_completion": calculate_profile_completion(profile),
        "skill_match_score": float(skill_gap.get("skill_match_score", 0.0) or 0.0),
        "roadmap_progress": float(roadmap.get("readiness_score", 0.0) or 0.0),
        "overall_readiness": overall_readiness,
        "projects": get_project_recommendations(selected_career),
        "certifications": get_certification_recommendations(selected_career),
        "selection_type": _selection_type(career_prediction),
        "ai_recommended_career": career_prediction.get("recommended_role"),
        "final_selected_career": selected_career,
    }
    return generate_career_report_pdf(user, profile, resume_data, career_prediction, skill_gap, roadmap, analytics_summary)


# --------------------------------------------------------------------------- #
# Admin (admin_dashboard_page)
# --------------------------------------------------------------------------- #
def get_admin_overview() -> Dict:
    selected = get_most_selected_careers()
    return clean({
        "overview": get_system_overview(),
        "career_summary": get_career_recommendation_summary(),
        "career_domains": get_career_domain_distribution(),
        "career_selection_counts": get_career_selection_counts(),
        "most_selected_careers": selected,
        "top_selected_career": selected[0]["career_role"] if selected else None,
        "top_selected_count": selected[0]["count"] if selected else 0,
        "override_stats": get_career_override_statistics(),
        "skill_summary": _pairs_to_objects(get_skill_gap_summary(), ["most_missing_skills", "most_common_skills"]),
        "resume_analytics": _pairs_to_objects(get_resume_analytics(), ["most_common_skills"]),
        "roadmap_analytics": _pairs_to_objects(get_roadmap_analytics(), ["most_generated_roadmaps"], key="career_role"),
        "database_health": get_database_health(),
        "latest_users": get_latest_registered_users(5),
        "user_activity": get_user_activity_scores(5),
    })


def _pairs_to_objects(data: Dict, keys: List[str], key: str = "skill") -> Dict:
    out = dict(data)
    for k in keys:
        out[k] = [{key: name, "count": int(count)} for name, count in data.get(k, [])]
    return out


def admin_search(name: Optional[str], email: Optional[str], career_role: Optional[str]) -> List[Dict]:
    """Same query as database.admin_db.search_users, with ONE fix: the inner
    SELECT says `cp1.user_id` instead of `user_id`. The original is rejected by
    MySQL ("Column 'user_id' in field list is ambiguous"), so the Streamlit admin
    search fails too. admin_db.py is left untouched; once you apply the same
    one-word fix there, this can simply call search_users()."""
    from database.admin_db import _execute_query

    query = (
        "SELECT u.id, u.name, u.email, u.created_at, p.interest_domain, cp.recommended_role, cp.confidence_score "
        "FROM users u "
        "LEFT JOIN profiles p ON p.user_id = u.id "
        "LEFT JOIN ("
        "  SELECT cp1.user_id, recommended_role, confidence_score, prediction_date "
        "  FROM career_predictions cp1 "
        "  JOIN (SELECT user_id, MAX(prediction_date) AS latest_prediction FROM career_predictions GROUP BY user_id) cp2 "
        "  ON cp1.user_id = cp2.user_id AND cp1.prediction_date = cp2.latest_prediction "
        ") cp ON cp.user_id = u.id "
        "WHERE 1=1 "
    )
    params: List = []
    if name:
        query += " AND u.name LIKE %s"
        params.append(f"%{name}%")
    if email:
        query += " AND u.email LIKE %s"
        params.append(f"%{email}%")
    if career_role:
        query += " AND cp.recommended_role LIKE %s"
        params.append(f"%{career_role}%")
    query += " ORDER BY u.created_at DESC"
    return clean(_execute_query(query, tuple(params)))
