"""Train and evaluate IntelliDesk's ticket-priority classifier."""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    PROJECT_ROOT / "ml" / "data" / "priority_training_data.csv"
)

MODEL_PATH = PROJECT_ROOT / "ml" / "ticket_priority_model.joblib"

EXPECTED_PRIORITIES = {
    "low",
    "medium",
    "high",
    "critical",
}


def load_dataset():
    """Load and validate labeled priority examples."""
    if not DATASET_PATH.is_file():
        raise FileNotFoundError(
            f"Priority training dataset not found: {DATASET_PATH}"
        )

    data = pd.read_csv(DATASET_PATH)

    required_columns = {"text", "priority"}

    if not required_columns.issubset(data.columns):
        raise ValueError(
            "Dataset must contain 'text' and 'priority' columns."
        )

    data = data[["text", "priority"]].dropna().copy()

    data["text"] = data["text"].astype(str).str.strip()
    data["priority"] = (
        data["priority"].astype(str).str.strip().str.lower()
    )

    data = data[
        (data["text"] != "")
        & (data["priority"] != "")
    ].copy()

    if data.empty:
        raise ValueError(
            "The priority dataset contains no usable examples."
        )

    actual_priorities = set(data["priority"].unique())

    if actual_priorities != EXPECTED_PRIORITIES:
        raise ValueError(
            "Dataset priorities do not match the expected classes. "
            f"Found: {sorted(actual_priorities)}"
        )

    if data["text"].duplicated().any():
        raise ValueError(
            "Duplicate ticket descriptions were found."
        )

    counts = data["priority"].value_counts()

    if (counts < 2).any():
        raise ValueError(
            "Every priority class must have at least two examples."
        )

    return data


def build_pipeline():
    """Create the priority text-classification pipeline."""
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )


def main():
    """Train, evaluate, and save the priority classifier."""
    data = load_dataset()

    print("=" * 65)
    print("INTELLIDESK — TICKET PRIORITY MODEL TRAINING")
    print("=" * 65)

    print(
        f"Dataset: {DATASET_PATH.relative_to(PROJECT_ROOT)}"
    )
    print(f"Usable examples: {len(data)}")
    print(f"Priority classes: {len(data['priority'].unique())}")

    print("\nExamples per priority:")
    print(
        data["priority"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    X = data["text"]
    y = data["priority"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    model = build_pipeline()
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    accuracy = accuracy_score(y_test, predictions)
    labels = sorted(EXPECTED_PRIORITIES)

    print("\n" + "-" * 65)
    print("HOLDOUT EVALUATION")
    print("-" * 65)
    print(f"Training examples: {len(X_train)}")
    print(f"Testing examples: {len(X_test)}")
    print(f"Holdout accuracy: {accuracy:.2%}")

    print("\nClassification report:")
    print(
        classification_report(
            y_test,
            predictions,
            labels=labels,
            zero_division=0,
        )
    )

    matrix = confusion_matrix(
        y_test,
        predictions,
        labels=labels,
    )

    print("Confusion matrix (rows=actual, columns=predicted):")
    print("Priority order:", labels)
    print(matrix)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    print(
        f"\nSaved trained model: "
        f"{MODEL_PATH.relative_to(PROJECT_ROOT)}"
    )

    print(
        "\nCaution: this model uses a small synthetic dataset. "
        "The holdout metrics are a development baseline and do not "
        "establish real-world priority prediction accuracy."
    )


if __name__ == "__main__":
    main()
