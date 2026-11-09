"""Reading foods for search (as the signed-in user, under RLS: foods are read-only)."""

import re

from psycopg import Connection

from app.db.food_ranking import Candidate, rank

# Misspellings: pg_trgm compares 3-letter chunks ("trigrams").
#   similarity(name, q)       whole-string; good for short names ("panner" ~ "Paneer" 0.40)
#   word_similarity(q, name)  best-matching PART of the name; good for long names
#                             ("toor dhal" ~ "Toor dal (split pigeon peas)" 0.60, but only 0.24 whole-string)
# Measured on our data (Step 4.6): 0.5 word similarity keeps "rice" away from "Ice cream" (0.40).
SIMILARITY_THRESHOLD = 0.3
WORD_SIMILARITY_THRESHOLD = 0.5
CANDIDATE_LIMIT = 60        # fetch a few more than we return, then rank in Python


def _any_word_pattern(query: str) -> str | None:
    """For a query of two or more words: a regex matching ANY of them as a whole word ("cooked rice" finds "Steamed white rice"
    too; ranking then puts foods with more of the words first). None for a single word, which then matches nothing here."""
    words = re.findall(r"[a-z0-9]{3,}", query.lower())
    return r"\y(" + "|".join(re.escape(w) for w in dict.fromkeys(words)) + r")\y" if len(words) >= 2 else None


def _like_pattern(query: str) -> str:
    """Escape LIKE wildcards so a user typing '%' or '_' matches those characters literally."""
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


SEARCH_SQL = """
select f.id, f.key, f.name, f.category, f.diet_class, f.is_dish, f.kcal_per_100g, f.protein_g_per_100g,
       f.carbs_g_per_100g, f.fat_g_per_100g, f.fiber_g_per_100g, f.review_status, f.source,
       coalesce(array_agg(s.synonym order by s.synonym) filter (where s.synonym is not null), '{}') as synonyms
from public.foods f
left join public.food_synonyms s on s.food_id = f.id
group by f.id
having bool_or(f.name ilike %(like)s or s.synonym ilike %(like)s)
    or bool_or(f.name ~* %(any_word)s or s.synonym ~* %(any_word)s)
    or max(greatest(extensions.similarity(f.name, %(q)s),
                    coalesce(extensions.similarity(s.synonym, %(q)s), 0))) > %(threshold)s
    or max(greatest(extensions.word_similarity(%(q)s, f.name),
                    coalesce(extensions.word_similarity(%(q)s, s.synonym), 0))) >= %(word_threshold)s
limit %(limit)s
"""


def get_food_for_portion(conn: Connection, key: str):
    """One food by its key with its values per 100 g and household units (None when the key is unknown)."""
    from app.db.meals import foods_for_logging   # local import: meals imports this module's neighbours

    row = conn.execute("select id from public.foods where key = %s", (key,)).fetchone()
    return foods_for_logging(conn, [row[0]]).get(row[0]) if row else None


def search_foods(conn: Connection, query: str, limit: int) -> list[dict]:
    """Foods whose name or local name contains the query (or looks similar), best first, with units."""
    rows = conn.execute(SEARCH_SQL, {"q": query, "like": _like_pattern(query),
                                     "any_word": _any_word_pattern(query), "threshold": SIMILARITY_THRESHOLD, "word_threshold": WORD_SIMILARITY_THRESHOLD,
                                     "limit": CANDIDATE_LIMIT}).fetchall()
    columns = ["id", "key", "name", "category", "diet_class", "is_dish", "kcal", "protein_g", "carbs_g",
               "fat_g", "fiber_g", "review_status", "source", "synonyms"]
    foods = {row[1]: dict(zip(columns, row)) for row in rows}
    candidates = [Candidate(f["key"], f["name"], f["category"], f["review_status"], tuple(f["synonyms"]))
                  for f in foods.values()]
    ranked = [foods[c.key] for c in rank(query, candidates)][:limit]

    ids = [f["id"] for f in ranked]
    units: dict[int, list[dict]] = {}
    if ids:
        for food_id, unit, grams in conn.execute(
            "select food_id, unit, grams from public.food_units where food_id = any(%s) order by unit", (ids,)
        ):
            units.setdefault(food_id, []).append({"unit": unit, "grams": float(grams)})
    for food in ranked:
        food["units"] = units.get(food["id"], [])
    return ranked
