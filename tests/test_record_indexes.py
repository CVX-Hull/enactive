"""Generated dated-record indexes (S-DOCS, #402)."""
from __future__ import annotations

from pathlib import Path

from tools import documents


def record(root: Path, name: str, date: str, scope: str, title: str, kind: str | None = "run",
           body: str = "Body.") -> None:
    kind_line = f"kind: {kind}\n" if kind else ""
    (root / "docs/acceptance" / name).write_text(
        f"---\nowner: lead\nstatus: historical\n{kind_line}date: '{date}'\nscope: '{scope}'\n---\n\n# {title}\n\n{body}\n")


def metadata_root(tmp_path: Path) -> Path:
    for directory in ("docs/acceptance", "docs/design", "schemas"):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "schemas/document.schema.json").write_text((documents.ROOT / "schemas/document.schema.json").read_text())
    for name in documents.ROOT_DOCUMENTS:
        (tmp_path / name).write_text("---\nowner: lead\nstatus: active\nreview_trigger: x\n---\n")
    return tmp_path


def test_a_dated_record_names_its_kind_and_the_index_shows_it(tmp_path):
    root = metadata_root(tmp_path)
    record(root, "2026-01-01-kindless.md", "2026-01-01", "No kind", "Kindless", kind=None)
    assert documents.check_metadata(root) == [
        "docs/acceptance/2026-01-01-kindless.md: a dated record names its kind in its front matter"]
    record(root, "2026-01-01-kindless.md", "2026-01-01", "Wrong kind", "Kindless", kind="note")
    assert "kind" in "\n".join(documents.check_metadata(root))
    record(root, "2026-01-01-kindless.md", "2026-01-01", "A study", "Kindless", kind="study")
    assert documents.check_metadata(root) == []
    assert "| [Kindless](2026-01-01-kindless.md) | study | A study |" in documents.render_index(root, "docs/acceptance/index.md")


def test_new_records_and_proposed_designs_open_with_at_a_glance(tmp_path):
    root = metadata_root(tmp_path)
    record(root, "2026-11-13-before.md", "2026-11-13", "Before the rule", "Before")
    assert documents.check_metadata(root) == []
    record(root, "2026-11-14-after.md", "2026-11-14", "After the rule", "After")
    assert documents.check_metadata(root) == [
        "docs/acceptance/2026-11-14-after.md: a dated record opens with '## At a glance'"]
    record(root, "2026-11-14-after.md", "2026-11-14", "After the rule", "After", body="## At a glance\n\nThe answer.")
    assert documents.check_metadata(root) == []
    design = root / "docs/design/note.md"
    design.write_text("---\nowner: lead\nstatus: proposed\nreview_trigger: x\n---\n\n# Note\n\nBody.\n")
    assert documents.check_metadata(root) == ["docs/design/note.md: a proposed design note opens with '## At a glance'"]
    design.write_text("---\nowner: lead\nstatus: proposed\nreview_trigger: x\n---\n\n# Note\n\n## At a glance\n\nShort.\n")
    assert documents.check_metadata(root) == []


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
        "---\nowner: lead\nstatus: historical\nkind: review\ndate: '2026-01-02'\nscope: Audit #400 of things\n---\n\n# Bare\n")
    assert documents.check_metadata(tmp_path) == [
        "docs/acceptance/2026-01-02-bare.md: quote a front-matter value containing ' #'; YAML reads the rest as a comment"]
