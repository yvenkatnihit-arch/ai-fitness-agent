"""Load data/foods_validated.csv into Supabase: public.foods + public.food_synonyms (Step 4.5a, D-039).

    uv run python -m fooddata.build              # first: regenerate the validated CSV
    uv run python -m fooddata.load --dry-run     # show what would change, then roll back
    uv run python -m fooddata.load               # load

Safe to re-run (idempotent): foods are upserted by `key`, so ids never change, and each
food's synonyms are replaced with the current local names. Everything happens in ONE
transaction: if any row fails, nothing is saved. Foods that are in the database but no
longer in the CSV are reported, never deleted (meal plans and logs may point to them).
"""

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import psycopg

from fooddata.build import VALIDATED

MACRO_MASS_LIMIT = 105  # same limit as the foods_macros_fit_in_100g constraint


@dataclass(frozen=True)
class FoodRow:
    key: str
    name: str
    category: str
    diet_class: str
    is_dish: bool
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None
    source: str
    source_ref: str
    review_status: str
    synonyms: tuple[str, ...]


def _number(row: dict, field: str, digits: int) -> float:
    try:
        return round(float(row[field]), digits)
    except ValueError:
        raise ValueError(f"{row['key']}: {field} is not a number ({row[field]!r})") from None


def synonyms_from(local_names: str, name: str) -> tuple[str, ...]:
    """'dahi;mosaru; Dahi ' -> ('dahi', 'mosaru'): trimmed, no blanks, no repeats, not the name itself."""
    seen, result = {name.strip().lower()}, []
    for part in local_names.split(";"):
        synonym = part.strip()
        if synonym and synonym.lower() not in seen:
            seen.add(synonym.lower())
            result.append(synonym)
    return tuple(result)


def to_food_row(row: dict) -> FoodRow:
    """One CSV row -> the values for public.foods, rounded to the column precision.
    Checks the same limits as the table's constraints, so a bad row gets a clear message."""
    if row["status"] not in ("ready", "review"):
        raise ValueError(f"{row['key']}: status {row['status']!r} must not be in the validated file")
    food = FoodRow(
        key=row["key"], name=row["name"], category=row["category"], diet_class=row["diet_class"],
        is_dish=row["category"].startswith("dish_"),
        kcal=_number(row, "kcal", 1), protein_g=_number(row, "protein_g", 2),
        carbs_g=_number(row, "carbs_g", 2), fat_g=_number(row, "fat_g", 2),
        fiber_g=_number(row, "fiber_g", 2) if row["fiber_g"] else None,
        source=row["source"], source_ref=row["source_id"], review_status=row["status"],
        synonyms=synonyms_from(row["local_names"], row["name"]),
    )
    if not 1 <= len(food.name) <= 120:
        raise ValueError(f"{food.key}: name must be 1-120 characters")
    if not 0 <= food.kcal <= 900:
        raise ValueError(f"{food.key}: kcal {food.kcal} outside 0-900")
    mass = food.protein_g + food.carbs_g + food.fat_g + (food.fiber_g or 0)
    if mass > MACRO_MASS_LIMIT:
        raise ValueError(f"{food.key}: macros + fibre = {mass:.1f} g per 100 g (limit {MACRO_MASS_LIMIT})")
    return food


def read_validated(path: Path = VALIDATED) -> list[FoodRow]:
    with path.open(encoding="utf-8", newline="") as handle:
        foods = [to_food_row(row) for row in csv.DictReader(handle)]
    keys = [f.key for f in foods]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise ValueError(f"duplicate keys: {duplicates}")
    return foods


UPSERT = """
insert into public.foods (key, name, category, diet_class, is_dish, kcal_per_100g, protein_g_per_100g,
                          carbs_g_per_100g, fat_g_per_100g, fiber_g_per_100g, source, source_ref, review_status)
values (%(key)s, %(name)s, %(category)s, %(diet_class)s, %(is_dish)s, %(kcal)s, %(protein_g)s,
        %(carbs_g)s, %(fat_g)s, %(fiber_g)s, %(source)s, %(source_ref)s, %(review_status)s)
on conflict (key) do update set
  name = excluded.name, category = excluded.category, diet_class = excluded.diet_class,
  is_dish = excluded.is_dish, kcal_per_100g = excluded.kcal_per_100g,
  protein_g_per_100g = excluded.protein_g_per_100g, carbs_g_per_100g = excluded.carbs_g_per_100g,
  fat_g_per_100g = excluded.fat_g_per_100g, fiber_g_per_100g = excluded.fiber_g_per_100g,
  source = excluded.source, source_ref = excluded.source_ref, review_status = excluded.review_status
returning id, (xmax = 0) as inserted
"""


@dataclass
class LoadResult:
    inserted: int = 0
    updated: int = 0
    synonyms: int = 0
    stale: tuple[str, ...] = ()


def load_foods(conn: psycopg.Connection, foods: list[FoodRow]) -> LoadResult:
    """Upsert every food and replace its synonyms. The caller commits or rolls back."""
    result = LoadResult()
    for food in foods:
        food_id, inserted = conn.execute(UPSERT, food.__dict__).fetchone()
        if inserted:
            result.inserted += 1
        else:
            result.updated += 1
        conn.execute("delete from public.food_synonyms where food_id = %s", (food_id,))
        for synonym in food.synonyms:
            conn.execute("insert into public.food_synonyms (food_id, synonym) values (%s, %s)", (food_id, synonym))
        result.synonyms += len(food.synonyms)
    rows = conn.execute("select key from public.foods where not (key = any(%s)) order by key",
                        ([f.key for f in foods],)).fetchall()
    result.stale = tuple(r[0] for r in rows)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="show what would change, then roll back")
    args = parser.parse_args()

    from app.core.config import get_settings  # only needed when talking to the database

    foods = read_validated()
    with psycopg.connect(get_settings().database_url.get_secret_value(), connect_timeout=10) as conn:
        result = load_foods(conn, foods)
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    verb = "would be" if args.dry_run else "were"
    print(f"{len(foods)} foods: {result.inserted} {verb} inserted, {result.updated} {verb} updated; "
          f"{result.synonyms} synonyms")
    ready = sum(f.review_status == "ready" for f in foods)
    print(f"review status: {ready} ready, {len(foods) - ready} review")
    if result.stale:
        print(f"in the database but not in the CSV (kept, not deleted): {', '.join(result.stale)}")
    if args.dry_run:
        print("dry run: nothing was saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
