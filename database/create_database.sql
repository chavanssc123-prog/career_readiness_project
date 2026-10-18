import os
import pickle
from typing import Dict, List

import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), "career_model.pkl")
LABEL_ENCODER_PATH = os.path.join(os.path.dirname(__file__), "label_encoder.pkl")
FEATURE_COLUMNS_PATH = os.path.join(os.path.dirname(__file__), "feature_columns.pkl")

TECHNICAL_SKILLS = [
    "Python",
    "Java",
    "SQL",
    "Excel",
    "Power BI",
    "Statistics",
    "Machine Learning",
    "Deep Learning",
    "HTML",
    "CSS",
    "JavaScript",
    "React",
    "NodeJS",
    "Spring Boot",
    "AWS",
    "Docker",
    "Kubernetes",
    "Linux",
    "Cyber Security",
]


def _load_model() -> object:
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Career model file not found. Train the model first.")
    with open(MODEL_PATH, "rb") as file:
        return pickle.load(file)


def _load_label_encoder() -> object:
    if not os.path.exists(LABEL_ENCODER_PATH):
        raise FileNotFoundError("Label encoder file not found. Train the model first.")
    with open(LABEL_ENCODER_PATH, "rb") as file:
        return pickle.load(file)


def _load_feature_columns() -> List[str]:
    if not os.path.exists(FEATURE_COLUMNS_PATH):
        raise FileNotFoundError("Feature columns file not found. Train the model first.")
    with open(FEATURE_COLUMNS_PATH, "rb") as file:
        return pickle.load(file)


def predict_career(profile_data: Dict[str, object], resume_data: Dict[str, List[str]]) -> List[Dict[str, object]]:
    model = _load_model()
    label_encoder = _load_label_encoder()
    feature_columns = _load_feature_columns()

    feature_vector = _build_feature_vector(profile_data, resume_data, feature_columns)
    probabilities = model.predict_proba([feature_vector])[0]
    labels = label_encoder.inverse_transform(np.arange(len(probabilities)))

    ranked = sorted(
        zip(labels, probabilities),
        key=lambda item: item[1],
        reverse=True,
    )

    top5 = [
        {"career": career, "confidence": float(score * 100)}
        for career, score in ranked[:5]
    ]
    return top5


def _build_feature_vector(profile_data: Dict[str, object], resume_data: Dict[str, List[str]], feature_columns: List[str]) -> List[object]:
    profile_interest = str(profile_data.get("Interest Domain", "")).strip().lower()
    report_skills = {skill.strip().lower() for skill in resume_data.get("skills", []) if skill}

    vector = []
    for column in feature_columns:
        if column in profile_data:
            vector.append(profile_data.get(column, 0))
            continue

        if column in TECHNICAL_SKILLS:
            vector.append(1 if column.lower() in report_skills else 0)
            continue

        if column.startswith("Interest Domain_"):
            category = column.replace("Interest Domain_", "").strip().lower()
            vector.append(1 if profile_interest == category else 0)
            continue

        vector.append(0)

    return vector
