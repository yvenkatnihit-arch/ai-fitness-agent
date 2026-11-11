"""Logging a meal from chat (Step 8.5, D-109): a PROPOSAL the user confirms, then a normal meal log.

The model only names foods (by key, from the food search), an amount and a unit. CODE then finds each food, turns the amount into grams
and calories and macros (app.calc.portions), builds the one-line summary the user reads, and saves a pending proposal. Nothing is logged
until the user approves; at approval the foods and amounts are resolved AGAIN from the database (the stored proposal carries no numbers
to trust), and the meal is written exactly like a meal logged on the form."""

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from app.calc.portions import PortionError, grams_for, nutrition_for, total
from app.core.time import india_today
from app.db import admin_transaction, user_transaction
from app.db import meals as meals_repo
from app.db import proposals as proposals_repo
from app.db import targets as targets_repo
from app.schemas.meals import LOG_BACKFILL_DAYS, MAX_ITEMS_PER_MEAL

SLOTS = ("breakfast", "mid_morning", "lunch", "evening_snack", "dinner", "other")
DAYS = ("today", "yesterday")
PROPOSAL_TYPE = "meal_log"


class MealLogError(Exception):
    """Something the person (or the model) can fix. str(e) is safe to show and tells what to change."""


def logged_on_for(day: str, today: date) -> date:
    if day not in DAYS:
        raise MealLogError("You can log a meal for today or yesterday.")
    return today if day == "today" else today - timedelta(days=1)


def resolve_items(conn, items: list[dict[str, Any]]) -> list[tuple[meals_repo.NewItem, str]]:
    """(item ready to write, the food's name) for each {food_key, quantity, unit}. Raises MealLogError with a fixable message."""
    if not 1 <= len(items) <= MAX_ITEMS_PER_MEAL:
        raise MealLogError(f"A meal needs 1 to {MAX_ITEMS_PER_MEAL} foods.")
    keys = [str(i["food_key"]) for i in items]
    ids = dict(conn.execute("select key, id from public.foods where key = any(%s)", (keys,)).fetchall())
    missing = [k for k in keys if k not in ids]
    if missing:
        raise MealLogError(f"These foods are not in our database: {', '.join(missing)}. Use a key returned by search_foods.")
    foods = meals_repo.foods_for_logging(conn, list(ids.values()))
    out = []
    for item in items:
        food = foods[ids[item["food_key"]]]
        try:
            grams = grams_for(float(item["quantity"]), str(item["unit"]), food.unit_grams)
        except PortionError as error:
            raise MealLogError(f"{food.name}: {error} Available units: {', '.join(['g', *sorted(food.unit_grams)])}.") from None
        out.append((meals_repo.NewItem(food.id, float(item["quantity"]), str(item["unit"]), grams, nutrition_for(grams, food.per_100g)), food.name))
    return out


def summary_for(slot: str, day: str, resolved: list[tuple[meals_repo.NewItem, str]], show_numbers: bool) -> str:
    foods = ", ".join(f"{name} {item.quantity:g} {item.unit} ({item.grams:g} g)" for item, name in resolved)
    text = f"Log for {slot.replace('_', ' ')} {day}: {foods}."
    if show_numbers:
        text += f" About {round(total([i.nutrition for i, _ in resolved]).kcal)} kcal."
    return text[:500]


def propose(user_id: UUID, slot: str, day: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Save a pending meal-log proposal and return what the chat shows. Raises MealLogError for anything fixable."""
    if slot not in SLOTS:
        raise MealLogError(f"The meal must be one of: {', '.join(SLOTS)}.")
    logged_on = logged_on_for(day, india_today())
    with user_transaction(user_id) as conn:
        resolved = resolve_items(conn, items)
        row = targets_repo.current_targets(conn)
    show_numbers = not (bool(row[6]) if row else False)                      # no calories for a user who must not see numbers
    summary = summary_for(slot, day, resolved, show_numbers)
    payload = {"slot": slot, "logged_on": logged_on.isoformat(),
               "items": [{"food_key": i["food_key"], "quantity": float(i["quantity"]), "unit": str(i["unit"])} for i in items]}
    with admin_transaction("chat: propose a meal log") as conn:
        saved = proposals_repo.replace_pending(conn, user_id, PROPOSAL_TYPE, summary, payload, source="chat")
    return {"proposal_id": str(saved[0]), "summary": summary,
            "will_log": [{"food": name, "amount": f"{i.quantity:g} {i.unit}", "grams": i.grams} for i, name in resolved]}


def apply(conn, user_id: UUID, payload: dict[str, Any]) -> None:
    """Write an approved meal log (on the admin connection of the approval, for this user). Re-resolves everything from the database."""
    from app.workflows.decide_proposal import ProposalCannotBeApplied   # local import: decide_proposal imports this module

    try:
        slot, logged_on = payload["slot"], date.fromisoformat(payload["logged_on"])
        if slot not in SLOTS:
            raise MealLogError("The meal slot is not valid.")
        today = india_today()
        if logged_on > today or logged_on < today - timedelta(days=LOG_BACKFILL_DAYS):
            raise MealLogError("That day is too long ago to log now. Please ask again.")
        resolved = resolve_items(conn, payload["items"])
    except (MealLogError, KeyError, ValueError, TypeError) as error:
        raise ProposalCannotBeApplied(str(error) if isinstance(error, MealLogError) else "This meal could not be saved. Please ask again.") from None
    meals_repo.insert_meal(conn, logged_on, slot, "chat", [item for item, _ in resolved], user_id=user_id)
