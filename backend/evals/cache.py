"""A tiny on-disk cache for eval replies (git-ignored), shared by the model-based evals (Step 7.7c, D-082).

Keyed by a hash of everything that could change the answer (model, prompt, input), so an unchanged case costs nothing and any
change to the prompt or model calls the model again.
"""

import hashlib
import json
from pathlib import Path

DIR = Path(__file__).with_name("cache")


def key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


class Cache:
    def __init__(self, name: str, enabled: bool = True) -> None:
        self.path, self.enabled = DIR / f"{name}.json", enabled
        self.data: dict = {}
        if enabled:
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.data = {}

    def get(self, k: str):
        return self.data.get(k)

    def put(self, k: str, value) -> None:
        self.data[k] = value

    def save(self) -> None:
        if self.enabled:
            self.path.parent.mkdir(exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")
