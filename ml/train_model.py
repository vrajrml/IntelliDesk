"""Train and evaluate IntelliDesk's ticket-category classifier."""

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
DATASET_PATH = PROJECT_ROOT / "ml" / "data" / "ticket_training_data.csv"
MODEL_PATH = PROJECT_ROOT / "ml" / "ticket_category_model.joblib"

EXPECTED_CATEGORIES = {
    "Hardware",
    "Software",
    "Network",
    "Account Access",
    "Email & Communication",
    "Other",
}


def load_dataset():
    """Load and validate labeled ticket examples."""
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Training dataset not found: {DATASET_PATH}"
        )

    data = pd.read_csv(DATASET_PATH)

    required_columns = {"text", "category"}
    if not required_columns.issubset(data.columns):
        raise ValueError(
            "Dataset must contain 'text' and 'category' columns."
        )

    data = data[["text", "category"]].dropna().copy()
    data["text"] = data["text"].astype(str).str.strip()
    data["category"] = data["category"].astype(str).str.strip()

    data = data[
        (data["text"] != "")
        & (data["category"] != "")
    ].copy()

    if data.empty:
        raise ValueError("The training dataset contains no usable examples.")

    actual_categories = set(data["category"].unique())
    if actual_categories != EXPECTED_CATEGORIES:
        raise ValueError(
            "Dataset categories do not match the expected categories. "
            f"Found: {sorted(actual_categories)}"
        )

    counts = data["category"].value_counts()
    if (counts < 2).any():
        raise ValueError(
            "Every category must have at least two examples."
        )

    if data.duplicated(subset=["text", "category"]).any():
        print("Warning: duplicate text/category pairs were found.")

    return data


def build_pipeline():
    """Create the text-classification pipeline."""
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
    """Train, evaluate, and save the classifier."""
    data = load_dataset()

    print("=" * 65)
    print("INTELLIDESK — TICKET CATEGORY MODEL TRAINING")
    print("=" * 65)

    print(f"Dataset: {DATASET_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Usable examples: {len(data)}")
    print(f"Categories: {len(data['category'].unique())}")

    print("\nExamples per category:")
    print(data["category"].value_counts().sort_index().to_string())

    X = data["text"]
    y = data["category"]

    # A stratified split preserves category representation in both sets.
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
            labels=sorted(EXPECTED_CATEGORIES),
            zero_division=0,
        )
    )

    labels = sorted(EXPECTED_CATEGORIES)
    matrix = confusion_matrix(y_test, predictions, labels=labels)

    print("Confusion matrix (rows=actual, columns=predicted):")
    print("Labels:", labels)
    print(matrix)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    print(f"\nSaved trained model: {MODEL_PATH.relative_to(PROJECT_ROOT)}")
    print(
        "\nNote: this model uses a small synthetic dataset. "
        "Its evaluation is a development baseline, not proof of "
        "real-world accuracy."
    )


if __name__ == "__main__":
    main()
