"""Order food search results (pure Python, no database): what someone most likely means.

Sort key, most important first:
  1. real text match before "looks similar" (trigram) matches
  2. foods eaten as they are (dishes, fruit, dairy...) before RAW staples (raw rice, dal, meat, fish),
     so "chawal" puts steamed rice above raw rice when logging a meal
  3. match quality: exact name/local name > exact CORE name (the name without its "(...)" note and
     split on "/": "Milk (whole)" and "Roti / chapati (no fat)" ARE "milk" and "roti") > the query as a
     whole word ("masoor dal") > the text starts with it ("dalda") > a word starts with it > contains it
  3b. for a query of two or more words, foods that contain more of the query's words come first, and the
     last word (the head noun: "rice" in "cooked rice") counts double, so "cooked rice" lists rice
     before dals that merely say "(cooked)"
  4. reviewed values ('ready') before 'review'
  5. shorter (more generic) names first, then alphabetical
"""

import re
from dataclasses import dataclass

# Ingredients in these categories are almost never eaten raw.
RAW_STAPLE_CATEGORIES = frozenset({"cereal", "pulse", "meat", "fish"})
# ...except these, which are eaten as they are.
EATEN_AS_IS = frozenset({"bread_white", "cornflakes", "tofu"})

EXACT, CORE_EXACT, WHOLE_WORD, PREFIX, WORD, CONTAINS, SIMILAR = range(7)


@dataclass(frozen=True)
class Candidate:
    key: str
    name: str
    category: str | None
    review_status: str
    synonyms: tuple[str, ...]


def normalise(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def cores(text: str) -> list[str]:
    """The name without its parenthetical note, split on "/": 'Roti / chapati (no fat)' -> ['roti', 'chapati']."""
    return [normalise(part) for part in re.sub(r"\([^)]*\)", " ", text).split("/") if normalise(part)]


def match_tier(query: str, texts: list[str]) -> int:
    """Best match of the query against the food's name and local names."""
    q = normalise(query)
    best = SIMILAR
    for text in texts:
        t = normalise(text)
        if t == q:
            return EXACT
        if q in cores(text):
            best = min(best, CORE_EXACT)
            continue
        if f" {q} " in f" {t} ":  # "dal" in "masoor dal": the whole word, not the start of "dalda"
            best = min(best, WHOLE_WORD)
        elif t.startswith(q):
            best = min(best, PREFIX)
        elif any(word.startswith(q) for word in t.split()) or f" {q}" in f" {t}":
            best = min(best, WORD)
        elif q in t:
            best = min(best, CONTAINS)
    return best


def is_raw_staple(c: Candidate) -> bool:
    return c.category in RAW_STAPLE_CATEGORIES and c.key not in EATEN_AS_IS


def words_score(query: str, texts: list[str]) -> int:
    """For a multi-word query: how many of its words the food contains as whole words (the last word counts double). 0 otherwise."""
    q = normalise(query).split()
    if len(q) < 2:
        return 0
    have = {w for text in texts for w in normalise(text).split()}
    return sum((2 if i == len(q) - 1 else 1) for i, w in enumerate(q) if w in have)


def rank(query: str, candidates: list[Candidate]) -> list[Candidate]:
    def key(c: Candidate):
        texts = [c.name, *c.synonyms]
        tier = match_tier(query, texts)
        return (tier == SIMILAR, -words_score(query, texts), is_raw_staple(c), tier, c.review_status != "ready", len(c.name), c.name)

    return sorted(candidates, key=key)
