"""The protein shortfall note (Step 7.10f, D-095). Plain code, no model: when a week's plan reaches clearly less protein than the
target, say so honestly and suggest what could close the gap, instead of leaving it as an "issue" in a collapsed panel.

Never shown for the kidney flag (its protein target is a CAP, so "eat more protein" would be wrong) and never to users whose
numbers are hidden (the server also strips it, see meal_plan_payload.hide_numbers)."""

from typing import Any

NOTE_BELOW_PERCENT = 85.0        # an average under this share of the protein target gets a note

# What could close the gap, by diet. Fixed text, never written by a model.
SUGGESTIONS = {
    "vegan": "tofu or tempeh, soya chunks, lentil and chickpea dishes, or a plant protein powder",
    "vegetarian": "paneer, Greek yogurt, milk, lentil dishes, or a protein powder",
    "eggetarian": "eggs, paneer, Greek yogurt, lentil dishes, or a protein powder",
    "non_vegetarian": "eggs, chicken, fish, Greek yogurt, or a protein powder",
}


def protein_shortfall(average_percent: float, diet_type: str, emphasis: str | None) -> dict[str, Any] | None:
    """{"percent": 48, "suggestions": "..."} when a note is due, else None."""
    if emphasis == "low_protein" or average_percent >= NOTE_BELOW_PERCENT:
        return None
    return {"percent": round(average_percent), "suggestions": SUGGESTIONS.get(diet_type, SUGGESTIONS["vegetarian"])}
