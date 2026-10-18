import os
import re
from typing import List, Dict, Optional

import pdfplumber
from PyPDF2 import PdfReader


def extract_text(file_path: str) -> str:
    """Extract text content from a PDF resume."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Resume file not found: {file_path}")

    extracted_text = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                extracted_text.append(page_text)
    except Exception:
        reader = PdfReader(file_path)
        for page in reader.pages:
            page_text = page.extract_text() or ""
            extracted_text.append(page_text)

    return "\n".join(extracted_text).strip()


def _normalize_text(text: str) -> str:
    return re.sub(r"[\r\n\t]+", " ", text).strip().lower()


def extract_skills(text: str) -> List[str]:
    skill_map = {
        "python": "Python",
        "java": "Java",
        "sql": "SQL",
        "excel": "Excel",
        "power bi": "Power BI",
        "statistics": "Statistics",
        "machine learning": "Machine Learning",
        "deep learning": "Deep Learning",
        "html": "HTML",
        "css": "CSS",
        "javascript": "JavaScript",
        "react": "React",
        "nodejs": "NodeJS",
        "spring boot": "Spring Boot",
        "aws": "AWS",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "linux": "Linux",
        "cyber security": "Cyber Security",
    }

    normalized = _normalize_text(text)
    found = []
    for skill_key, skill_name in skill_map.items():
        pattern = rf"\b{re.escape(skill_key)}\b"
        if re.search(pattern, normalized, re.IGNORECASE):
            found.append(skill_name)

    return found


def extract_education(text: str) -> List[str]:
    education_options = ["BCA", "BSc", "BTech", "MCA", "MSc", "MTech"]
    normalized = text
    education_found = []
    for option in education_options:
        pattern = rf"\b{re.escape(option)}\b"
        if re.search(pattern, normalized, re.IGNORECASE):
            education_found.append(option)
    return education_found


def extract_certifications(text: str) -> List[str]:
    normalized = _normalize_text(text)
    certification_patterns = [
        r"certified in ([a-z0-9 \-&]+)",
        r"certificate in ([a-z0-9 \-&]+)",
        r"certification in ([a-z0-9 \-&]+)",
        r"completed ([a-z0-9 \-&]+) certification",
    ]

    certifications = []
    for pattern in certification_patterns:
        for match in re.findall(pattern, normalized, flags=re.IGNORECASE):
            candidate = match.strip().title()
            if candidate and candidate not in certifications:
                certifications.append(candidate)

    # fallback: look for common certification phrases
    if not certifications:
        fallback_phrases = [
            "aws certified",
            "google certified",
            "microsoft certified",
            "oracle certified",
            "pmp",
            "scrum master",
            "data science",
        ]
        for phrase in fallback_phrases:
            if phrase in normalized and phrase.title() not in certifications:
                certifications.append(phrase.title())

    return certifications


def extract_projects(text: str) -> List[str]:
    normalized = text
    project_sections = re.split(r"\n{2,}|projects?|project work", normalized, flags=re.IGNORECASE)
    projects = []

    if len(project_sections) > 1:
        for section in project_sections[1:]:
            lines = [line.strip() for line in section.splitlines() if line.strip()]
            for line in lines[:5]:
                if len(line) > 10 and not re.search(r"(education|experience|skills|certification|certifications?)", line, re.IGNORECASE):
                    projects.append(line)
            if projects:
                break

    if not projects:
        headings = re.findall(r"(?:Project|Projects)[:\-\s]*(.+)", text, flags=re.IGNORECASE)
        for heading in headings:
            candidate = heading.strip()
            if candidate and candidate not in projects:
                projects.append(candidate)

    return projects


def parse_resume(file_path: str) -> Dict[str, List[str]]:
    text = extract_text(file_path)
    skills = extract_skills(text)
    education = extract_education(text)
    certifications = extract_certifications(text)
    projects = extract_projects(text)

    return {
        "skills": skills,
        "education": education,
        "certifications": certifications,
        "projects": projects,
    }
