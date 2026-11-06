"""Turn data/ingredients.csv (our hand-picked mappings) and our recipes (fooddata/recipes.py)
into validated foods plus a review report.

    uv run python -m fooddata.build

Writes:
  data/foods_validated.csv          rows with no errors (warnings allowed), ready for loading (Step 4.5)
  data/reports/ingredients_review.md  every row with its values, status and flags, for a human to check

Statuses:  ready    = all checks passed
           review   = passed, but a warning needs a human look
           blocked  = an error; NOT written to foods_validated.csv
           gap      = no trustworthy source yet (recorded, never filled with a substitute)
"""

import csv
from pathlib import Path

from fooddata.carbs import available_carbs
from fooddata.checks import Issue, check_diet_class, check_dish_plausibility, check_food, compare_sources
from fooddata.download import DATA_DIR
from fooddata.find import load_all
from fooddata.records import FoodRecord
from fooddata.recipes import read_recipes, review_recipes
from fooddata.review import STATUSES, Reviewed
from fooddata.units import Unit, build_units, read_unit_rows, recipe_keys, usda_portions, write_units

INGREDIENTS = DATA_DIR / "ingredients.csv"
VALIDATED = DATA_DIR / "foods_validated.csv"
REPORT = DATA_DIR / "reports" / "ingredients_review.md"

COLUMNS = ["key", "name", "local_names", "category", "diet_class", "source", "source_id",
           "check_source", "check_id", "match", "note"]
DIET_CLASSES = {"vegan", "vegetarian", "eggetarian", "non_vegetarian"}
MATCHES = {"exact", "close", "none"}


def review_row(row: dict, index: dict[tuple[str, str], FoodRecord]) -> Reviewed:
    result = Reviewed(row)
    if row["diet_class"] not in DIET_CLASSES:
        result.add(Issue("mapping", "error", f"unknown diet class {row['diet_class']!r}"))
    if row["match"] not in MATCHES:
        result.add(Issue("mapping", "error", f"unknown match {row['match']!r}"))
    if result.issues:  # the row itself is invalid: the checks below depend on these values
        result.status = "blocked"
        return result
    if row["match"] == "none" or not row["source"]:
        result.status = "gap"
        return result

    food = index.get((row["source"], row["source_id"]))
    if food is None:
        result.add(Issue("mapping", "error", f"{row['source']} id {row['source_id']} not found"))
        result.status = "blocked"
        return result
    result.food = food

    carbs = available_carbs(food)
    result.carbs_g, result.carbs_quality = carbs.grams, carbs.quality
    if carbs.grams is None:
        result.add(Issue("carbs", "error", carbs.note))
    elif carbs.quality == "approximate":
        result.add(Issue("carbs", "warning", carbs.note))

    result.add(*check_food(food))
    result.add(*check_dish_plausibility(row["category"], food.kcal))
    # Diet rules run on BOTH the source's name and ours, so a mislabelled mapping is caught.
    result.add(*check_diet_class(food.name, food.category, row["diet_class"]))
    result.add(*check_diet_class(f"{row['name']} {row['local_names']}", None, row["diet_class"]))

    if row["check_source"]:
        other = index.get((row["check_source"], row["check_id"]))
        if other is None:
            result.add(Issue("mapping", "error", f"cross-check id {row['check_source']} {row['check_id']} not found"))
        else:
            result.add(*compare_sources(food, other))

    if any(i.severity == "error" for i in result.issues):
        result.status = "blocked"
    elif result.issues or row["match"] == "close":
        result.status = "review"
    return result


def read_ingredients(path: Path = INGREDIENTS) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"{path.name} columns are {reader.fieldnames}, expected {COLUMNS}")
        rows = list(reader)
    keys = [r["key"] for r in rows]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise ValueError(f"duplicate keys in {path.name}: {duplicates}")
    return rows


def _fmt(value: float | None) -> str:
    return "?" if value is None else f"{value:.1f}"


def write_outputs(results: list[Reviewed]) -> None:
    with VALIDATED.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["key", "name", "local_names", "category", "diet_class", "source", "source_id",
                         "source_name", "kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "carbs_quality", "match", "status"])
        for r in results:
            if r.status in ("ready", "review"):
                f = r.food
                writer.writerow([r.row["key"], r.row["name"], r.row["local_names"], r.row["category"],
                                 r.row["diet_class"], f.source, f.source_id, f.name, f.kcal, f.protein_g,
                                 round(r.carbs_g, 2), f.fat_g, f.fiber_g, r.carbs_quality, r.row["match"], r.status])

    REPORT.parent.mkdir(exist_ok=True)
    counts = {s: sum(r.status == s for r in results) for s in ("ready", "review", "blocked", "gap")}
    lines = [
        "# Ingredient review report",
        "",
        "Generated by `uv run python -m fooddata.build` from `data/ingredients.csv` and our recipes "
        "(`data/recipes.csv` + `data/recipe_items.csv`, source `computed`). Values are per 100 g (cooked, for dishes).",
        "Recipes stay in *To review* until `reviewed_by` is filled in `data/recipes.csv`.",
        "Carbs = available carbohydrate as weighed (D-038). `?` = not measured in the source.",
        "",
        f"**{len(results)} ingredients:** {counts['ready']} ready · {counts['review']} to review · "
        f"{counts['blocked']} blocked · {counts['gap']} gaps",
        "",
        "## What to check",
        "- **Blocked:** an error; not loaded until fixed (wrong id, can't convert carbs, impossible values, diet rule).",
        "- **Review:** loaded, but please confirm: a warning, or a *close* (not exact) match.",
        "- **Gap:** no trustworthy source yet; nothing is substituted.",
        "",
    ]
    for status, title in (("blocked", "Blocked"), ("review", "To review"), ("gap", "Gaps"), ("ready", "Ready")):
        group = [r for r in results if r.status == status]
        if not group:
            continue
        lines += [f"## {title} ({len(group)})", "",
                  "| Ingredient | Diet | Source | kcal | Protein | Carbs | Fat | Fibre | Flags / notes |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in group:
            f = r.food
            source = f"{f.source} `{f.source_id}`<br><sub>{f.name[:60]}</sub>" if f else "none"
            flags = [f"**{i.severity}** {i.check}: {i.message}" for i in r.issues]
            if r.row["match"] == "close":
                flags.append("close match")
            if r.row["note"]:
                flags.append(r.row["note"])
            values = [_fmt(f.kcal), _fmt(f.protein_g), _fmt(r.carbs_g), _fmt(f.fat_g), _fmt(f.fiber_g)] if f else ["", "", "", "", ""]
            lines.append(f"| {r.row['name']} | {r.row['diet_class']} | {source} | " + " | ".join(values)
                         + " | " + "<br>".join(flags) + " |")
        lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def write_units_report(units: list[Unit], errors: list[str]) -> None:
    """Append the household units to the review report, so one file shows everything to check."""
    lines = ["", f"## Household units ({len(units)} ok, {len(errors)} blocked)", "",
             "From `data/food_units.csv`. katori = 150 ml, glass = 250 ml (D-040).", ""]
    lines += [f"- **BLOCKED** {e}" for e in errors]
    lines += ["", "| Food | Unit | Grams | How we know |", "|---|---|---|---|"]
    lines += [f"| {u.key} | {u.unit} | {u.grams:g} | {u.source} |" for u in units]
    with REPORT.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    index = {(f.source, f.source_id): f for f in load_all()}
    results = [review_row(row, index) for row in read_ingredients()]
    # Recipes (Step 4.4) are built from the ingredients that passed: ready or review.
    usable = {r.row["key"]: r for r in results if r.status in ("ready", "review")}
    recipes, items = read_recipes()
    clash = sorted({r["key"] for r in recipes} & {r.row["key"] for r in results})
    if clash:
        raise ValueError(f"keys in both ingredients.csv and recipes.csv: {clash}")
    results += review_recipes(recipes, items, usable)
    write_outputs(results)
    for status in STATUSES:
        print(f"{status:<8} {sum(r.status == status for r in results)}")
    for r in results:
        if r.status == "blocked":
            print(f"  BLOCKED {r.row['key']}: " + "; ".join(i.message for i in r.issues if i.severity == "error"))

    # Household units (Step 4.5b) for the foods that made it into foods_validated.csv.
    food_sources = {r.row["key"]: (r.food.source, r.food.source_id) for r in results if r.status in ("ready", "review")}
    units, errors = build_units(food_sources, usda_portions(), recipe_keys(), read_unit_rows())
    write_units(units)
    write_units_report(units, errors)
    print(f"units    {len(units)} ok, {len(errors)} blocked")
    for error in errors:
        print(f"  BLOCKED unit {error}")
    print(f"report: {REPORT.relative_to(DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
