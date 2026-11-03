"""Predict ticket priority using the trained IntelliDesk ML model."""

from functools import lru_cache
from pathlib import Path

import joblib


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "ml" / "ticket_priority_model.joblib"

ALLOWED_PRIORITIES = {
    "low",
    "medium",
    "high",
    "critical",
}


@lru_cache(maxsize=1)
def load_model():
    """Load the trained priority model once and reuse it."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"Priority model not found: {MODEL_PATH}"
        )

    return joblib.load(MODEL_PATH)


def predict_priority(title, description):
    """
    Predict a ticket's priority.

    Returns:
        dict containing:
            priority: predicted priority label
            confidence: estimated model probability from 0 to 1
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
    predicted_priority = str(model.classes_[best_index])

    if predicted_priority not in ALLOWED_PRIORITIES:
        raise ValueError(
            f"Unexpected priority predicted by model: "
            f"{predicted_priority}"
        )

    return {
        "priority": predicted_priority,
        "confidence": float(probabilities[best_index]),
    }
