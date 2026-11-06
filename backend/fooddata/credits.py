"""The app's "Data sources" page content, generated from data/sources.json (Step 4.8).

Licences require it: UK CoFID (Open Government Licence v3.0) needs a visible credit and a link to
the licence; USDA asks to be cited. The frontend can't read data/ when deployed (Vercel builds only
frontend/), so `fooddata.build` writes frontend/src/sources/credits.json, and a test checks that the
committed file matches the current data (like a migration: generated, committed, never hand-edited).
"""

import csv
import json
from pathlib import Path

from fooddata.download import DATA_DIR, MANIFEST

CREDITS = DATA_DIR.parent / "frontend" / "src" / "sources" / "credits.json"

RECIPES_NOTE = {
    "key": "computed",
    "name": "Our own recipes",
    "description": (
        "Dishes such as idli, dosa, upma and kheer are not in the sources above. We calculate them from "
        "a recipe: raw ingredient weights (from the sources above) plus the weight of the cooked dish. "
        "The maths is done by tested code, never by AI. A recipe shows \"values being checked\" until a "
        "person has reviewed it."
    ),
}
NOTES = [
    "Values are per 100 g. Carbs are digestible carbohydrate; fibre is shown separately.",
    "Foods marked \"values being checked\" are still being reviewed against a second source.",
    "Household measures: 1 katori = 150 ml and 1 glass = 250 ml; piece and spoon weights come from USDA's measured portions.",
]


def build_credits(manifest: dict, validated_rows: list[dict]) -> dict:
    """Only sources we actually use, each with how many of our foods come from it."""
    counts: dict[str, int] = {}
    for row in validated_rows:
        counts[row["source"]] = counts.get(row["source"], 0) + 1
    sources = [
        {key: s[key] for key in ("key", "name", "release", "license", "license_url", "credit", "homepage")}
        | {"foods": counts[s["key"]]}
        for s in manifest["sources"] if counts.get(s["key"])
    ]
    unknown = sorted(set(counts) - {s["key"] for s in manifest["sources"]} - {"computed"})
    if unknown:
        raise ValueError(f"foods come from sources missing in sources.json: {unknown}")
    recipes = [RECIPES_NOTE | {"foods": counts["computed"]}] if counts.get("computed") else []
    return {"sources": sources, "recipes": recipes, "notes": NOTES}


def current_credits(validated: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    with validated.open(encoding="utf-8", newline="") as handle:
        return build_credits(manifest, list(csv.DictReader(handle)))


def render(credits: dict) -> str:
    return json.dumps(credits, indent=2, ensure_ascii=False) + "\n"


def write_credits(validated: Path, path: Path = CREDITS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(current_credits(validated)), encoding="utf-8", newline="\n")
