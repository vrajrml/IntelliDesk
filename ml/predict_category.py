"""Predict ticket categories using the trained IntelliDesk ML model."""

from functools import lru_cache
from pathlib import Path

import joblib


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "ml" / "ticket_category_model.joblib"


@lru_cache(maxsize=1)
def load_model():
    """Load the trained model once and reuse it."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"Ticket category model not found: {MODEL_PATH}"
        )

    return joblib.load(MODEL_PATH)


def predict_category(title, description):
    """
    Predict a ticket category and return its confidence.

    Returns:
        dict: {
            "category": predicted category name,
            "confidence": probability between 0 and 1
        }
    """
    title = (title or "").strip()
    description = (description or "").strip()

    if not title and not description:
        raise ValueError(
            "A ticket title or description is required for prediction."
        )

    text = f"{title}. {description}".strip()

    model = load_model()
    probabilities = model.predict_proba([text])[0]

    best_index = probabilities.argmax()

    return {
        "category": str(model.classes_[best_index]),
        "confidence": float(probabilities[best_index]),
    }
