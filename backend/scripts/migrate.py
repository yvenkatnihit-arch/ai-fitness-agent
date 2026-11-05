"""Apply new SQL migrations in supabase/migrations/ to the database in backend/.env (D-024).

Run from backend/:
    uv run python scripts/migrate.py            # apply new migrations
    uv run python scripts/migrate.py --dry-run  # only show what would be applied

The database URL is read from .env and never printed.
"""

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.checkpointer import setup_checkpointer_tables  # noqa: E402
from app.core.config import get_settings  # noqa: E402

SUPABASE_CLI = "supabase@2.121.0"  # pinned, see D-024
REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    npx = shutil.which("npx")
    if npx is None:
        print("npx not found. Install Node.js (see CLAUDE.md -> Commands).")
        return 1

    db_url = get_settings().database_url.get_secret_value()
    args = [npx, "--yes", SUPABASE_CLI, "db", "push", "--db-url", db_url, *sys.argv[1:]]

    # The CLI asks "Do you want to push these migrations? [Y/n]"; answer yes.
    result = subprocess.run(
        args, cwd=REPO_ROOT, input="y\n", capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    output = (result.stdout + result.stderr).replace(db_url, "***")
    print(output.strip())
    if result.returncode != 0 or "--dry-run" in sys.argv:
        return result.returncode

    # LangGraph manages its own tables; create/upgrade them in the `langgraph` schema (D-012).
    setup_checkpointer_tables()
    print("LangGraph checkpointer tables ready (schema: langgraph).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
