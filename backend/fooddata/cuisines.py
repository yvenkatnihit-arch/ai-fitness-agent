"""Cuisines in the food data (Step 7.10c, D-090).

Each ingredient and recipe row has a `cuisines` column: one or more names separated by `;` (blank means Indian, so older rows keep
working). The data pipeline accepts every PLANNED cuisine, so we can build and review its foods early. The APP only enables a cuisine
(app.core.vocabulary.CUISINES) after its foods are loaded, and the loader refuses to load a food that belongs to a cuisine the app has
not enabled yet. Adding a cuisine = add it here, build and review its data, then enable it in the app (one step, D-088).
"""

PLANNED = ("indian", "mediterranean")
DEFAULT = ("indian",)


def parse(value: str | None) -> tuple[str, ...]:
    """'indian; mediterranean' -> ('indian', 'mediterranean'). Blank or missing -> Indian."""
    parts = tuple(p.strip().lower() for p in (value or "").split(";") if p.strip())
    return parts or DEFAULT


def problems(value: str | None) -> list[str]:
    """What is wrong with a cuisines cell (empty list = fine)."""
    parts = parse(value)
    out = []
    unknown = sorted({p for p in parts if p not in PLANNED})
    if unknown:
        out.append(f"unknown cuisine(s) {unknown}; planned cuisines are {list(PLANNED)}")
    if len(set(parts)) != len(parts):
        out.append("a cuisine is listed twice")
    return out


def to_cell(cuisines: tuple[str, ...]) -> str:
    return ";".join(cuisines)
