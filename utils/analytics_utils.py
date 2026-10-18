import pandas as pd
from typing import Dict, List, Optional

from utils.profile_utils import calculate_profile_completion
from utils.resume_utils import calculate_resume_completeness
from utils.skill_gap_utils import format_skill_list


def normalize_comma_separated_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def calculate_resume_ats_score(resume_data: Dict) -> float:
    skills = normalize_comma_separated_list(resume_data.get("skills"))
    projects = normalize_comma_separated_list(resume_data.get("projects"))
    certifications = normalize_comma_separated_list(resume_data.get("certifications"))
    education = normalize_comma_separated_list(resume_data.get("education"))
    return float(calculate_resume_completeness(skills, projects, certifications, education))


def infer_career_category(recommended_role: Optional[str]) -> str:
    if not recommended_role:
        return "Unknown"

    role = recommended_role.lower()
    if "data" in role or "scientist" in role or "analyst" in role:
        return "Data & Analytics"
    if "cloud" in role or "devops" in role or "engineer" in role:
        return "Cloud & Infrastructure"
    if "full stack" in role or "developer" in role or "java" in role or "web" in role:
        return "Software Development"
    return "Other"


def compute_overall_readiness(
    profile_completion: float,
    ats_score: float,
    skill_match_score: float,
    roadmap_progress: float,
) -> float:
    values = [profile_completion, ats_score, skill_match_score, roadmap_progress]
    return round(min(sum(values) / 4.0, 100.0), 2)


def generate_analytics_insights(
    profile: Optional[Dict],
    resume_data: Optional[Dict],
    career_prediction: Optional[Dict],
    skill_gap: Optional[Dict],
    roadmap: Optional[Dict],
    profile_completion: float,
    ats_score: float,
    skill_match_score: float,
    roadmap_progress: float,
) -> List[str]:
    insights: List[str] = []

    if not profile:
        insights.append("Complete your profile to unlock the analytics dashboard.")
        return insights

    if profile_completion < 60:
        insights.append("Your profile completion is low. Add more experience, internships, and certifications.")

    if int(profile.get("internship_count", 0) or 0) == 0:
        insights.append("Your profile is strong but lacks internships. Add internship experience to improve readiness.")

    if ats_score < 70:
        insights.append("Your resume ATS score is below 70%. Add resume keywords and structure key achievements clearly.")

    if not career_prediction:
        insights.append("Generate a career recommendation to activate career and skill gap analytics.")
    else:
        if career_prediction.get("confidence_score", 0) < 70:
            insights.append("Your career recommendation confidence is low. Improve profile and resume details for stronger results.")

    if skill_gap:
        missing_skills = normalize_comma_separated_list(skill_gap.get("missing_skills"))
        if missing_skills:
            top_missing = ", ".join(format_skill_list(missing_skills)[:3])
            insights.append(f"Focus on missing skills: {top_missing}.")
        if float(skill_gap.get("skill_match_score", 0) or 0) >= 80:
            insights.append("Your skill match is strong. Keep refining your strengths and building relevant projects.")
    else:
        insights.append("Complete skill gap analysis to see matched, missing, and extra skills.")

    if roadmap:
        if roadmap_progress >= 80:
            insights.append("Your roadmap readiness is strong. Keep following your learning milestones.")
        else:
            insights.append("Use the roadmap steps to raise your readiness score and close remaining gaps.")
    else:
        insights.append("Generate a personalized roadmap to convert recommendations into a learning plan.")

    if career_prediction and "data scientist" in career_prediction.get("recommended_role", "").lower():
        if not any(skill in skill_gap.get("missing_skills", "").lower() for skill in ["machine learning", "statistics"]):
            insights.append("For a Data Scientist role, focus on Machine Learning and Statistics if they are missing.")

    return insights


def build_skill_gap_counts(skill_gap: Optional[Dict]) -> Dict[str, int]:
    if not skill_gap:
        return {"Matched": 0, "Missing": 0, "Extra": 0}
    matched = normalize_comma_separated_list(skill_gap.get("matched_skills"))
    missing = normalize_comma_separated_list(skill_gap.get("missing_skills"))
    extra = normalize_comma_separated_list(skill_gap.get("extra_skills"))
    return {
        "Matched": len(matched),
        "Missing": len(missing),
        "Extra": len(extra),
    }
