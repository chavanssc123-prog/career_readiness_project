from typing import Dict, List

CAREER_PROJECT_RECOMMENDATIONS = {
    "Data Analyst": [
        "House Price Prediction",
        "Customer Segmentation Analysis",
        "Sales Dashboard with Power BI",
    ],
    "Data Scientist": [
        "House Price Prediction",
        "Customer Churn Prediction",
        "Sentiment Analysis with NLP",
    ],
    "Business Analyst": [
        "Business Performance Dashboard",
        "Market Research Report",
        "Customer Requirement Analysis",
    ],
    "Full Stack Developer": [
        "E-Commerce Website",
        "Job Portal",
        "Task Management App",
    ],
    "Java Developer": [
        "REST API with Spring Boot",
        "Inventory Management System",
        "Employee Management Portal",
    ],
    "Cloud Engineer": [
        "AWS Deployment Project",
        "Docker and Kubernetes Microservice",
        "Cloud Infrastructure Automation",
    ],
}

CAREER_CERTIFICATIONS = {
    "Data Analyst": [
        "Google Data Analytics Professional Certificate",
        "Microsoft Certified: Data Analyst Associate",
    ],
    "Data Scientist": [
        "IBM Data Science Professional Certificate",
        "Google Professional Machine Learning Engineer",
    ],
    "Business Analyst": [
        "IIBA ECBA",
        "Certified Business Analysis Professional (CBAP)",
    ],
    "Full Stack Developer": [
        "AWS Certified Developer Associate",
        "Microsoft Certified: Azure Developer Associate",
    ],
    "Java Developer": [
        "Oracle Certified Professional: Java SE",
        "Spring Professional Certification",
    ],
    "Cloud Engineer": [
        "AWS Certified Solutions Architect",
        "Certified Kubernetes Administrator (CKA)",
    ],
}

ROADMAP_TEMPLATES = {
    "high": [
        "Focus on the top missing skills and complete one major project.",
        "Build practical hands-on experience with targeted courses.",
        "Refine interview-ready artifacts and review fundamentals.",
    ],
    "medium": [
        "Improve technical depth with guided practice and projects.",
        "Fill remaining gaps with online courses and certifications.",
        "Prepare a strong portfolio and resume summary.",
    ],
    "low": [
        "Strengthen existing skills and showcase experience.",
        "Polish projects and add advanced learning goals.",
        "Practice mock interviews and refine communication.",
    ],
}


def get_project_recommendations(career_role: str) -> List[str]:
    return CAREER_PROJECT_RECOMMENDATIONS.get(career_role, [
        "Build a domain-specific capstone project.",
        "Create a portfolio showcasing your best work.",
    ])


def get_certification_recommendations(career_role: str) -> List[str]:
    return CAREER_CERTIFICATIONS.get(career_role, [
        "Complete a recognized industry certification.",
        "Take a role-specific specialization course.",
    ])


def build_monthly_roadmap(
    career_role: str,
    missing_skills: List[str],
    readiness_score: float,
) -> Dict[str, List[str]]:
    missing_skills_formatted = [skill.title() for skill in missing_skills]
    roadmap = {
        "Month 1": [],
        "Month 2": [],
        "Month 3": [],
    }

    priority = "medium"
    if readiness_score < 50:
        priority = "high"
    elif readiness_score >= 80:
        priority = "low"

    if missing_skills_formatted:
        roadmap["Month 1"].append("Learn and practice: " + ", ".join(missing_skills_formatted[:2]))
        roadmap["Month 2"].append("Build a project using: " + ", ".join(missing_skills_formatted[:3]))
        roadmap["Month 3"].append("Review and polish skills: " + ", ".join(missing_skills_formatted))
    else:
        roadmap["Month 1"].append("Consolidate your current skill set and fill small gaps.")
        roadmap["Month 2"].append("Build a career-relevant project and add it to your portfolio.")
        roadmap["Month 3"].append("Prepare interview-ready summaries and practice real-world problems.")

    templates = ROADMAP_TEMPLATES.get(priority, ROADMAP_TEMPLATES["medium"])
    roadmap["Month 1"].append(templates[0])
    roadmap["Month 2"].append(templates[1])
    roadmap["Month 3"].append(templates[2])

    return roadmap


def build_roadmap_summary(
    career_role: str,
    roadmap: Dict[str, List[str]],
    projects: List[str],
    certifications: List[str],
) -> str:
    lines = [
        f"Career Role: {career_role}",
        "\n",
        "Roadmap:\n",
    ]
    for month, goals in roadmap.items():
        lines.append(f"{month}: \n")
        for goal in goals:
            lines.append(f"- {goal}\n")
    lines.append("\nRecommended Projects:\n")
    for project in projects:
        lines.append(f"- {project}\n")
    lines.append("\nRecommended Certifications:\n")
    for cert in certifications:
        lines.append(f"- {cert}\n")
    return "\n".join(lines)
