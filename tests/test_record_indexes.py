"""Generated dated-record indexes (S-DOCS, #402)."""
from __future__ import annotations

from pathlib import Path

from tools import documents


def record(root: Path, name: str, date: str, scope: str, title: str) -> None:
    (root / "docs/acceptance" / name).write_text(
        f"---\nowner: lead\nstatus: historical\ndate: '{date}'\nscope: '{scope}'\n---\n\n# {title}\n\nBody.\n")


def test_index_lists_records_newest_first_and_detects_staleness(tmp_path):
    (tmp_path / "docs/acceptance").mkdir(parents=True)
    (tmp_path / "docs/changes").mkdir()
    record(tmp_path, "2026-01-01-old.md", "2026-01-01", "First | piped", "Old record")
    record(tmp_path, "2026-02-01-new.md", "2026-02-01", "Second", "New record")
    assert documents.check_indexes(tmp_path) == [f"{i}: stale; run python -m tools.documents --write"
                                                  for i in documents.INDEXES]
    for index in documents.INDEXES:
        (tmp_path / index).write_text(documents.render_index(tmp_path, index))
    assert documents.check_indexes(tmp_path) == []
    text = (tmp_path / "docs/acceptance/index.md").read_text()
    new, old = text.index("[New record](2026-02-01-new.md)"), text.index("[Old record](2026-01-01-old.md)")
    assert new < old and "First \\| piped" in text and "index.md)" not in text.split("| --- |")[-1]
    record(tmp_path, "2026-03-01-added.md", "2026-03-01", "Third", "Added")
    assert documents.check_indexes(tmp_path) == ["docs/acceptance/index.md: stale; run python -m tools.documents --write"]


def test_undated_or_statusless_records_sort_last_without_crashing(tmp_path):
    (tmp_path / "docs/acceptance").mkdir(parents=True)
    record(tmp_path, "2026-01-01-dated.md", "2026-01-01", "Dated", "Dated record")
    (tmp_path / "docs/acceptance/zz-undated.md").write_text("---\nowner: lead\n---\n\n# Undated\n")
    text = documents.render_index(tmp_path, "docs/acceptance/index.md")
    assert text.index("[Dated record]") < text.index("| undated | [Undated](zz-undated.md) |  |  |")


def test_an_unquoted_hash_in_front_matter_is_rejected(tmp_path):
    (tmp_path / "docs/acceptance").mkdir(parents=True)
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas/document.schema.json").write_text((documents.ROOT / "schemas/document.schema.json").read_text())
    for name in documents.ROOT_DOCUMENTS:
        (tmp_path / name).write_text("---\nowner: lead\nstatus: active\nreview_trigger: x\n---\n")
    record(tmp_path, "2026-01-01-quoted.md", "2026-01-01", "Audit #400 of things", "Quoted")
    assert documents.check_metadata(tmp_path) == []
    (tmp_path / "docs/acceptance/2026-01-02-bare.md").write_text(
        "---\nowner: lead\nstatus: historical\ndate: '2026-01-02'\nscope: Audit #400 of things\n---\n\n# Bare\n")
    assert documents.check_metadata(tmp_path) == [
        "docs/acceptance/2026-01-02-bare.md: quote a front-matter value containing ' #'; YAML reads the rest as a comment"]
