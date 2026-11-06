"""Download checks with small fake files (no network)."""

import json
import zipfile

import pytest

from fooddata import download as d


def make_zip(path, members):
    with zipfile.ZipFile(path, "w") as archive:
        for name in members:
            archive.writestr(name, "id,name\n1,test\n")
    return path


SOURCE = {"key": "test", "expect_members": ["food.csv", "nutrient.csv"], "sha256": None}


def test_a_complete_archive_passes_and_gets_a_hash(tmp_path):
    path = make_zip(tmp_path / "ok.zip", ["FoodData/food.csv", "FoodData/nutrient.csv"])  # nested folder is fine
    result = d.verify(SOURCE, path)
    assert len(result["sha256"]) == 64 and result["size_bytes"] > 0


def test_missing_expected_files_are_refused(tmp_path):
    path = make_zip(tmp_path / "partial.zip", ["food.csv"])
    with pytest.raises(d.SourceError, match="nutrient.csv"):
        d.verify(SOURCE, path)


def test_an_html_error_page_saved_as_zip_is_refused(tmp_path):
    path = tmp_path / "fake.zip"
    path.write_text("<html>Service unavailable</html>")
    with pytest.raises(d.SourceError, match="not a zip"):
        d.verify(SOURCE, path)


def test_changed_upstream_data_is_refused(tmp_path):
    path = make_zip(tmp_path / "data.zip", ["food.csv", "nutrient.csv"])
    recorded = {**SOURCE, "sha256": "0" * 64}  # what we recorded last time
    with pytest.raises(d.SourceError, match="upstream data changed"):
        d.verify(recorded, path)


def test_same_file_as_recorded_passes(tmp_path):
    path = make_zip(tmp_path / "data.zip", ["food.csv", "nutrient.csv"])
    recorded = {**SOURCE, "sha256": d.sha256_of(path)}
    assert d.verify(recorded, path)["sha256"] == recorded["sha256"]


def test_every_source_in_the_manifest_has_licence_credit_and_https_url():
    manifest = json.loads(d.MANIFEST.read_text(encoding="utf-8"))
    for source in manifest["sources"]:
        assert source["url"].startswith("https://"), source["key"]
        assert source["license"] and source["credit"], source["key"]
        # what "complete" means depends on the format: archive members, or keys of each JSON item
        assert source["expect_keys"] if source.get("format") == "json" else source["expect_members"], source["key"]
