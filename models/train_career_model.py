import os
import pickle
from typing import List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
from sklearn.tree import DecisionTreeClassifier


DATASET_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "datasets",
    "AI_Career_Readiness_Dataset_1200.xlsx",
)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "career_model.pkl")
LABEL_ENCODER_PATH = os.path.join(os.path.dirname(__file__), "label_encoder.pkl")
FEATURE_COLUMNS_PATH = os.path.join(os.path.dirname(__file__), "feature_columns.pkl")


TECHNICAL_SKILLS = [
    "python",
    "java",
    "sql",
    "excel",
    "power_bi",
    "statistics",
    "machine_learning",
    "deep_learning",
    "html",
    "css",
    "javascript",
    "react",
    "nodejs",
    "spring_boot",
    "aws",
    "docker",
    "kubernetes",
    "linux",
    "cyber_security",
]

NUMERIC_COLUMNS = [
    "cgpa",
    "communication",
    "logical_reasoning",
    "projects_count",
    "certifications_count",
    "internship_count",
]

CATEGORICAL_COLUMN = "interest_domain"
TARGET_COLUMN = "career_role"


def load_dataset() -> pd.DataFrame:
    """
    Load dataset and normalize column names.
    """

    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(
            f"Dataset not found:\n{DATASET_PATH}"
        )

    print("\nLoading Dataset...")
    df = pd.read_excel(DATASET_PATH)

    # Normalize columns
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    print("\nDataset Columns Found:")
    print(df.columns.tolist())

    return df


def audit_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Dataset Audit
    """

    summary = pd.DataFrame(
        {
            "missing_values": df.isnull().sum(),
            "unique_values": df.nunique(),
            "dtype": df.dtypes,
        }
    )

    summary["duplicate_rows"] = df.duplicated().sum()

    return summary


def preprocess_dataset(
    df: pd.DataFrame,
) -> Tuple[np.ndarray, np.ndarray, LabelEncoder, List[str]]:

    print("\nStarting Preprocessing...")

    df = df.copy()

    df.drop_duplicates(inplace=True)

    required_columns = (
        NUMERIC_COLUMNS
        + TECHNICAL_SKILLS
        + [CATEGORICAL_COLUMN, TARGET_COLUMN]
    )

    print("\nExpected Columns:")
    print(required_columns)

    for column in required_columns:
        if column not in df.columns:
            raise ValueError(
                f"Required dataset column missing: {column}"
            )

    # Numeric columns
    df[NUMERIC_COLUMNS] = (
        df[NUMERIC_COLUMNS]
        .apply(pd.to_numeric, errors="coerce")
    )

    df[NUMERIC_COLUMNS] = (
        df[NUMERIC_COLUMNS]
        .fillna(df[NUMERIC_COLUMNS].median())
    )

    # Skills
    df[TECHNICAL_SKILLS] = (
        df[TECHNICAL_SKILLS]
        .fillna(0)
    )

    # Interest Domain
    df[CATEGORICAL_COLUMN] = (
        df[CATEGORICAL_COLUMN]
        .fillna("Unknown")
        .astype(str)
    )

    X_numeric = (
        df[NUMERIC_COLUMNS]
        .astype(float)
        .values
    )

    X_skills = (
        df[TECHNICAL_SKILLS]
        .astype(float)
        .values
    )

    try:
        interest_encoder = OneHotEncoder(
            handle_unknown="ignore",
            sparse_output=False,
        )
    except TypeError:
        interest_encoder = OneHotEncoder(
            handle_unknown="ignore",
            sparse=False,
        )

    interest_encoded = interest_encoder.fit_transform(
        df[[CATEGORICAL_COLUMN]]
    )

    if hasattr(interest_encoded, "toarray"):
        interest_encoded = interest_encoded.toarray()

    try:
        interest_feature_names = (
            interest_encoder
            .get_feature_names_out([CATEGORICAL_COLUMN])
            .tolist()
        )
    except AttributeError:
        interest_feature_names = (
            interest_encoder
            .get_feature_names([CATEGORICAL_COLUMN])
            .tolist()
        )

    interest_feature_names = [
        str(name).strip().lower().replace(" ", "_")
        for name in interest_feature_names
    ]

    X = np.hstack(
        [
            X_numeric,
            X_skills,
            interest_encoded,
        ]
    )

    feature_names = (
        NUMERIC_COLUMNS
        + TECHNICAL_SKILLS
        + interest_feature_names
    )

    label_encoder = LabelEncoder()

    y = label_encoder.fit_transform(
        df[TARGET_COLUMN].astype(str)
    )

    print("Preprocessing Completed")
    print(f"Dataset shape: {df.shape}")
    print(f"Feature count: {len(feature_names)}")

    return X, y, label_encoder, feature_names


def train_and_select_model(X, y):

    print("\nTraining Models...")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y,
    )

    models = {
        "RandomForest": RandomForestClassifier(
            n_estimators=200,
            random_state=42,
        ),
        "DecisionTree": DecisionTreeClassifier(
            random_state=42,
        ),
        "LogisticRegression": LogisticRegression(
            max_iter=2000,
            random_state=42,
        ),
    }

    best_model_name = None
    best_model = None
    best_accuracy = 0

    results = {}

    for name, model in models.items():

        print(f"\nTraining: {name}")

        model.fit(X_train, y_train)

        predictions = model.predict(X_test)

        accuracy = accuracy_score(
            y_test,
            predictions,
        )

        results[name] = {
            "accuracy": accuracy,
            "confusion_matrix": confusion_matrix(
                y_test,
                predictions,
            ).tolist(),
            "classification_report": classification_report(
                y_test,
                predictions,
                output_dict=True,
            ),
        }

        print(f"{name} Accuracy: {accuracy:.4f}")

        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_model_name = name
            best_model = model

    return (
        best_model_name,
        best_model,
        best_accuracy,
        results,
    )


def save_artifacts(
    model,
    label_encoder,
    feature_names,
):

    with open(MODEL_PATH, "wb") as file:
        pickle.dump(model, file)

    with open(LABEL_ENCODER_PATH, "wb") as file:
        pickle.dump(label_encoder, file)

    with open(FEATURE_COLUMNS_PATH, "wb") as file:
        pickle.dump(feature_names, file)

    print("\nModel Artifacts Saved Successfully")
    print(MODEL_PATH)
    print(LABEL_ENCODER_PATH)
    print(FEATURE_COLUMNS_PATH)


def main():

    print("\nAI Career Recommendation Model Training")

    df = load_dataset()

    audit = audit_dataset(df)

    print("\nDataset Audit Summary:")
    print(audit)

    X, y, label_encoder, feature_names = preprocess_dataset(df)

    (
        best_model_name,
        best_model,
        best_accuracy,
        results,
    ) = train_and_select_model(X, y)

    print("\nBest Model Selected:")
    print(best_model_name)

    print(f"\nBest Accuracy: {best_accuracy:.4f}")

    save_artifacts(
        best_model,
        label_encoder,
        feature_names,
    )

    print("\nTraining Completed Successfully")


if __name__ == "__main__":
    main()