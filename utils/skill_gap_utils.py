from typing import Dict, List, Set, Tuple

CAREER_SKILL_REQUIREMENTS = {
    "Data Analyst": [
        "Python",
        "SQL",
        "Excel",
        "Power BI",
        "Statistics",
    ],
    "Data Scientist": [
        "Python",
        "SQL",
        "Statistics",
        "Machine Learning",
        "Deep Learning",
        "Power BI",
    ],
    "Business Analyst": [
        "Excel",
        "SQL",
        "Power BI",
        "Communication",
    ],
    "Full Stack Developer": [
        "HTML",
        "CSS",
        "JavaScript",
        "React",
        "NodeJS",
        "SQL",
    ],
    "Java Developer": [
        "Java",
        "Spring Boot",
        "SQL",
    ],
    "Cloud Engineer": [
        "AWS",
        "Docker",
        "Kubernetes",
        "Linux",
    ],
}

SKILL_PRIORITY_MAP = {
    "python": "High",
    "sql": "High",
    "machine learning": "High",
    "deep learning": "High",
    "java": "High",
    "spring boot": "High",
    "aws": "High",
    "docker": "High",
    "kubernetes": "High",
    "react": "High",
    "nodejs": "High",
    "html": "Medium",
    "css": "Medium",
    "javascript": "Medium",
    "power bi": "Medium",
    "excel": "Medium",
    "linux": "Medium",
    "statistics": "Medium",
    "communication": "Medium",
    "spring": "Medium",
    "cyber security": "Low",
    "project experience": "Low",
    "certifications": "Low",
    "internship experience": "Low",
    "logical reasoning": "Medium",
}


def normalize_skill(skill: str) -> str:
    if not skill:
        return ""
    return skill.strip().lower().replace("\n", " ").strip()


def build_current_skills(profile_data: Dict[str, object], resume_data: Dict[str, List[str]]) -> Set[str]:
    resume_skills = [normalize_skill(skill) for skill in resume_data.get("skills", []) if skill]
    skills = {skill for skill in resume_skills if skill}

    if int(profile_data.get("communication", 0) or 0) >= 7:
        skills.add("communication")
    if int(profile_data.get("logical_reasoning", 0) or 0) >= 7:
        skills.add("logical reasoning")
    if int(profile_data.get("projects_count", 0) or 0) > 0:
        skills.add("project experience")
    if int(profile_data.get("certifications_count", 0) or 0) > 0:
        skills.add("certifications")
    if int(profile_data.get("internship_count", 0) or 0) > 0:
        skills.add("internship experience")
    interest = str(profile_data.get("interest_domain", "") or "").strip()
    if interest:
        skills.add(normalize_skill(interest))

    return skills


def get_required_skills_for_career(career_role: str) -> List[str]:
    return CAREER_SKILL_REQUIREMENTS.get(career_role, [])


def compute_skill_gap(
    career_role: str,
    current_skills: Set[str],
) -> Tuple[List[str], List[str], List[str]]:
    required_skills = [normalize_skill(skill) for skill in get_required_skills_for_career(career_role)]
    required_set = {skill for skill in required_skills if skill}
    matched_skills = sorted(skill for skill in required_set if skill in current_skills)
    missing_skills = sorted(skill for skill in required_set if skill not in current_skills)
    extra_skills = sorted(skill for skill in current_skills if skill not in required_set)
    return matched_skills, missing_skills, extra_skills


def calculate_skill_match_score(matched_skills: List[str], required_skills: List[str]) -> float:
    if not required_skills:
        return 0.0
    return round((len(matched_skills) / len(required_skills)) * 100.0, 2)


def calculate_readiness_score(skill_match_score: float, profile_data: Dict[str, object]) -> float:
    cgpa_score = min(max(float(profile_data.get("cgpa", 0) or 0) / 10.0, 0.0), 1.0) * 20.0
    communication_score = min(max(int(profile_data.get("communication", 0) or 0) / 10.0, 0.0), 1.0) * 15.0
    projects_score = min(int(profile_data.get("projects_count", 0) or 0), 5) / 5.0 * 15.0
    internships_score = min(int(profile_data.get("internship_count", 0) or 0), 2) / 2.0 * 10.0
    skill_score = min(max(skill_match_score / 100.0, 0.0), 1.0) * 40.0

    total = skill_score + cgpa_score + communication_score + projects_score + internships_score
    return round(min(total, 100.0), 2)


def categorize_skills_by_priority(skills: List[str]) -> Dict[str, List[str]]:
    categories = {"High Priority": [], "Medium Priority": [], "Low Priority": []}
    for skill in skills:
        priority = SKILL_PRIORITY_MAP.get(skill.lower(), "Medium")
        categories[f"{priority} Priority"].append(skill)
    return categories


SKILL_DISPLAY_OVERRIDES = {
    "python": "Python",
    "sql": "SQL",
    "power bi": "Power BI",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "html": "HTML",
    "css": "CSS",
    "javascript": "JavaScript",
    "nodejs": "NodeJS",
    "spring boot": "Spring Boot",
    "aws": "AWS",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "linux": "Linux",
    "cyber security": "Cyber Security",
    "communication": "Communication",
    "statistics": "Statistics",
    "project experience": "Project Experience",
    "certifications": "Certifications",
    "internship experience": "Internship Experience",
    "logical reasoning": "Logical Reasoning",
}


def format_skill_list(skills: List[str]) -> List[str]:
    formatted = []
    for skill in skills:
        normalized = normalize_skill(skill)
        if not normalized:
            continue
        formatted.append(SKILL_DISPLAY_OVERRIDES.get(normalized, skill.title()))
    return formatted
