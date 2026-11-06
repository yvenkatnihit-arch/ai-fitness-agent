"""Run every check over the full downloaded datasets and print a summary.

    uv run python -m fooddata.audit

This doesn't import anything. It shows how clean each source is before we choose foods from it.
"""

from collections import Counter

from fooddata.checks import check_food, find_duplicates
from fooddata.cofid import read_cofid
from fooddata.download import MANIFEST, RAW_DIR
from fooddata.usda import read_sr_legacy

import json


def main() -> None:
    files = {s["key"]: RAW_DIR / s["file"] for s in json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]}
    datasets = {
        "usda_sr_legacy": read_sr_legacy(files["usda_sr_legacy"]),
        "uk_cofid": read_cofid(files["uk_cofid"]),
    }
    for key, foods in datasets.items():
        counts: Counter[tuple[str, str]] = Counter()
        examples: dict[tuple[str, str], str] = {}
        clean = 0
        for food in foods:
            issues = check_food(food)
            if not issues:
                clean += 1
            for issue in issues:
                counts[(issue.check, issue.severity)] += 1
                examples.setdefault((issue.check, issue.severity), f"{food.name[:55]}: {issue.message}")
        print(f"\n{key}: {len(foods)} foods, {clean} pass every check ({100 * clean / len(foods):.1f} %)")
        for (check, severity), n in counts.most_common():
            print(f"  {severity:<7} {check:<11} {n:>5}   e.g. {examples[(check, severity)]}")
        print(f"  duplicate names: {len(find_duplicates(foods))} groups")


if __name__ == "__main__":
    main()
