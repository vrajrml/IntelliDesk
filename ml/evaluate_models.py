"""Evaluate IntelliDesk's existing saved ML models."""

from pathlib import Path

import joblib
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split


ROOT = Path(__file__).resolve().parent.parent
ML_DIR = ROOT / "ml"
DATA_DIR = ML_DIR / "data"

MODELS = {
    "CATEGORY": {
        "dataset": DATA_DIR / "ticket_training_data.csv",
        "model": ML_DIR / "ticket_category_model.joblib",
        "target": "category",
        "classes": [
            "Account Access",
            "Email & Communication",
            "Hardware",
            "Network",
            "Other",
            "Software",
        ],
    },
    "PRIORITY": {
        "dataset": DATA_DIR / "priority_training_data.csv",
        "model": ML_DIR / "ticket_priority_model.joblib",
        "target": "priority",
        "classes": [
            "critical",
            "high",
            "low",
            "medium",
        ],
    },
}


def evaluate_model(name, settings):
    """Evaluate one saved model using its original holdout split."""

    print("\n" + "=" * 75)
    print(f"{name} MODEL EVALUATION")
    print("=" * 75)

    dataset_path = settings["dataset"]
    model_path = settings["model"]
    target = settings["target"]
    expected_classes = settings["classes"]

    if not dataset_path.is_file():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}"
        )

    if not model_path.is_file():
        raise FileNotFoundError(
            f"Saved model not found: {model_path}"
        )

    data = pd.read_csv(dataset_path)

    required_columns = {"text", target}

    if not required_columns.issubset(data.columns):
        raise ValueError(
            f"{dataset_path.name} must contain "
            f"the columns: {sorted(required_columns)}"
        )

    data = data[["text", target]].dropna().copy()

    data["text"] = data["text"].astype(str).str.strip()
    data[target] = data[target].astype(str).str.strip()

    if target == "priority":
        data[target] = data[target].str.lower()

    data = data[
        (data["text"] != "")
        & (data[target] != "")
    ].copy()

    actual_classes = sorted(data[target].unique())

    if actual_classes != sorted(expected_classes):
        raise ValueError(
            f"Unexpected classes in {dataset_path.name}: "
            f"{actual_classes}"
        )

    if data.duplicated(subset=["text", target]).any():
        print("WARNING: Duplicate text/label pairs detected.")

    print(f"Dataset: {dataset_path.relative_to(ROOT)}")
    print(f"Saved model: {model_path.relative_to(ROOT)}")
    print(f"Total usable examples: {len(data)}")
    print(f"Number of classes: {len(actual_classes)}")

    print("\nClass distribution:")
    print(data[target].value_counts().sort_index().to_string())

    X = data["text"]
    y = data[target]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    model = joblib.load(model_path)

    model_classes = sorted(
        str(label) for label in model.classes_
    )

    if model_classes != sorted(expected_classes):
        raise ValueError(
            "Saved model classes do not match expected classes. "
            f"Found: {model_classes}"
        )

    predictions = model.predict(X_test)

    probabilities = model.predict_proba(X_test)

    accuracy = accuracy_score(y_test, predictions)

    print("\nDataset split:")
    print(f"Training examples: {len(X_train)}")
    print(f"Testing examples: {len(X_test)}")

    print("\nOverall accuracy:")
    print(f"{accuracy:.2%}")

    print("\nClassification report:")
    print(
        classification_report(
            y_test,
            predictions,
            labels=expected_classes,
            zero_division=0,
            digits=4,
        )
    )

    matrix = confusion_matrix(
        y_test,
        predictions,
        labels=expected_classes,
    )

    print("Confusion matrix:")
    print("Rows = Actual | Columns = Predicted")
    print("Class order:", expected_classes)
    print(matrix)

    confidence = probabilities.max(axis=1)
    correct = (predictions == y_test.to_numpy())

    print("\nPrediction confidence:")
    print(f"Mean confidence: {confidence.mean():.2%}")
    print(f"Minimum confidence: {confidence.min():.2%}")
    print(f"Maximum confidence: {confidence.max():.2%}")

    print("\nConfidence groups:")

    confidence_groups = [
        (0.0, 0.50),
        (0.50, 0.60),
        (0.60, 0.70),
        (0.70, 0.80),
        (0.80, 0.90),
        (0.90, 1.01),
    ]

    for lower, upper in confidence_groups:
        mask = (
            (confidence >= lower)
            & (confidence < upper)
        )

        count = int(mask.sum())

        if count:
            group_accuracy = correct[mask].mean()

            print(
                f"{lower:.0%}–{min(upper, 1.0):.0%}: "
                f"{count} predictions, "
                f"{group_accuracy:.2%} accuracy"
            )

    print("\nModel evaluation completed: PASS")

    return {
        "name": name,
        "accuracy": accuracy,
        "training_samples": len(X_train),
        "testing_samples": len(X_test),
        "classes": len(actual_classes),
    }


def main():
    print("=" * 75)
    print("INTELLIDESK — ML MODEL EVALUATION")
    print("=" * 75)

    print(
        "Evaluating existing saved models. "
        "No model will be retrained or overwritten."
    )

    results = []

    for name, settings in MODELS.items():
        results.append(
            evaluate_model(name, settings)
        )

    print("\n" + "=" * 75)
    print("FINAL MODEL COMPARISON")
    print("=" * 75)

    for result in results:
        print(f"\n{result['name']}")
        print(f"  Accuracy: {result['accuracy']:.2%}")
        print(f"  Training samples: {result['training_samples']}")
        print(f"  Testing samples: {result['testing_samples']}")
        print(f"  Classes: {result['classes']}")

    print("\nBoth saved ML models were evaluated successfully.")
    print("No database records or model files were modified.")


if __name__ == "__main__":
    main()
