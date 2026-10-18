from typing import List, Dict

CAREER_FEATURES = [
    "cgpa",
    "communication",
    "logical_reasoning",
    "projects_count",
    "certifications_count",
    "internship_count",
    "interest_domain",
]


def build_profile_features(profile: Dict) -> Dict[str, object]:
    return {
        "cgpa": float(profile.get("cgpa", 0.0) or 0.0),
        "communication": int(profile.get("communication", 0) or 0),
        "logical_reasoning": int(profile.get("logical_reasoning", 0) or 0),
        "projects_count": int(profile.get("projects_count", 0) or 0),
        "certifications_count": int(profile.get("certifications_count", 0) or 0),
        "internship_count": int(profile.get("internship_count", 0) or 0),
        "interest_domain": profile.get("interest_domain", "Unknown") or "Unknown",
    }


def build_resume_features(resume_data: Dict) -> Dict[str, List[str]]:
    return {
        "skills": resume_data.get("skills", "").split(", ") if resume_data.get("skills") else [],
        "projects": resume_data.get("projects", "").split(", ") if resume_data.get("projects") else [],
        "certifications": resume_data.get("certifications", "").split(", ") if resume_data.get("certifications") else [],
        "education": resume_data.get("education", "").split(", ") if resume_data.get("education") else [],
    }
