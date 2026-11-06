"""Search both datasets by name, to choose an ingredient's exact source food.

    uv run python -m fooddata.find "pigeon peas" "paneer" "finger millet"

A query matches foods whose name (or category) contains ALL its words. Shows id, values per
100 g, and available carbs (D-038), so mappings are picked deliberately, never auto-matched.
"""

import json
import sys

from fooddata.carbs import available_carbs
from fooddata.cofid import read_cofid
from fooddata.download import MANIFEST, RAW_DIR
from fooddata.records import FoodRecord
from fooddata.usda import read_sr_legacy

MAX_RESULTS = 6


def load_all() -> list[FoodRecord]:
    files = {s["key"]: RAW_DIR / s["file"] for s in json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]}
    return read_sr_legacy(files["usda_sr_legacy"]) + read_cofid(files["uk_cofid"])


def search(foods: list[FoodRecord], query: str) -> list[FoodRecord]:
    words = query.lower().split()
    hits = [f for f in foods if all(w in f"{f.name} {f.category or ''}".lower() for w in words)]
    return sorted(hits, key=lambda f: (len(f.name), f.name))  # shortest (most generic) names first


def describe(food: FoodRecord) -> str:
    carbs = available_carbs(food).grams
    fmt = lambda v: "  ?" if v is None else f"{v:5.1f}"  # noqa: E731
    return (f"{food.source:<14} {food.source_id:<8} kcal {fmt(food.kcal)} P {fmt(food.protein_g)} "
            f"C {fmt(carbs)} F {fmt(food.fat_g)} fib {fmt(food.fiber_g)}  {food.name[:70]}")


def main(queries: list[str]) -> None:
    foods = load_all()
    for query in queries:
        hits = search(foods, query)
        print(f"\n## {query}  ({len(hits)} matches)")
        for food in hits[:MAX_RESULTS]:
            print("  " + describe(food))


if __name__ == "__main__":
    main(sys.argv[1:])
