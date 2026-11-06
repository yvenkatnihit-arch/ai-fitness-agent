"""Download the open food datasets listed in data/sources.json into data/raw/ (D-037).

    uv run python -m fooddata.download          # download what's missing, verify everything
    uv run python -m fooddata.download --check  # verify existing files only, no network

For each file it checks it is a complete, readable archive with the expected contents, then
records size, SHA-256 and download date in data/sources.json. If a file we already recorded
changes upstream (different SHA-256), it stops instead of silently using different data.
"""

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MANIFEST = DATA_DIR / "sources.json"
RAW_DIR = DATA_DIR / "raw"


class SourceError(Exception):
    """A downloaded file is incomplete, unexpected, or different from what we recorded."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_archive(path: Path, expect_members: list[str]) -> None:
    """Both the USDA CSV zips and .xlsx files are zip archives: test them and their contents."""
    if not zipfile.is_zipfile(path):
        raise SourceError(f"{path.name} is not a zip/xlsx archive (incomplete download or an error page?)")
    with zipfile.ZipFile(path) as archive:
        broken = archive.testzip()
        if broken:
            raise SourceError(f"{path.name}: corrupt member {broken}")
        names = {Path(name).name for name in archive.namelist()} | set(archive.namelist())
        missing = [member for member in expect_members if member not in names]
        if missing:
            raise SourceError(f"{path.name}: expected files missing: {missing}")


def verify(source: dict, path: Path) -> dict:
    """Check the file and return its size/hash. Refuses a file whose hash changed since we recorded it."""
    check_archive(path, source["expect_members"])
    digest = sha256_of(path)
    if source.get("sha256") and source["sha256"] != digest:
        raise SourceError(
            f"{source['key']}: file differs from the recorded SHA-256. The upstream data changed. "
            "Review the new release before accepting it (clear sha256 in sources.json to re-record)."
        )
    return {"sha256": digest, "size_bytes": path.stat().st_size}


def download(url: str, target: Path) -> None:
    partial = target.with_suffix(target.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_bytes(1 << 20):
                handle.write(chunk)
    partial.replace(target)  # only a finished download gets the real name


def run(check_only: bool) -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    RAW_DIR.mkdir(exist_ok=True)
    ok = True
    for source in manifest["sources"]:
        path = RAW_DIR / source["file"]
        try:
            if not path.exists():
                if check_only:
                    raise SourceError(f"{source['key']}: {path.name} not downloaded yet")
                print(f"downloading {source['name']} ...")
                download(source["url"], path)
                source["downloaded_at"] = datetime.now(UTC).isoformat(timespec="seconds")
            source.update(verify(source, path))
            print(f"OK  {source['key']:<16} {source['size_bytes'] / 1e6:6.1f} MB  sha256 {source['sha256'][:12]}…")
        except (SourceError, httpx.HTTPError) as error:
            ok = False
            print(f"ERR {source['key']}: {error}")
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify existing files only (no network)")
    sys.exit(run(parser.parse_args().check))
