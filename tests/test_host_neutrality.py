"""Current design, harness and tooling name no specific player host or coding agent.

Only the adapter, setup and operator pages may name them. Historical and superseded
records, dated control exercises/reviews and external citations are evidence and
stay untouched; internal link destinations are paths, not prose.
"""
import json
from pathlib import Path
import re
import sys

import frontmatter

ROOT = Path(__file__).resolve().parents[1]
# `pi` as a lowercase word is not a host name; only the capitalized product name is.
PRODUCT = re.compile(r"\bPi\b|pi-player-host|pi-agent-core|pi-ai\b|pi-mcp|earendil|[Cc]odex|CODEX|[Cc]laude|CLAUDE")
# An external citation (title and URL), an internal link destination, or a bare URL.
CITATIONS = re.compile(r"\[[^\]]*\]\(https?://[^)]*\)|\]\([^)]*\)|https?://\S+")
ALLOWED = (
    "tools/player_host/",     # current adapter
    "docs/operations/",       # operator procedures, including coding-agent hosts
    "docs/setup.md",
    "docs/environment.md",
    "docs/operator-permissions.md",
    "docs/runbook.md",        # operations index
    "NOTICE.md",              # third-party attribution
)
ROOT_DOCUMENTS = ("README.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md", "NOTICE.md")
REGISTRY = "docs/control-registry.json"
# Rendered from the registry, which is checked structurally below.
GENERATED = ("docs/controls.md",)
DATED_RECORDS = ("last_exercise", "maintenance_review")


def current(path: Path) -> bool:
    if path.suffix != ".md":
        return True
    status = frontmatter.loads(path.read_text(encoding="utf-8")).metadata.get("status")
    return status not in ("historical", "superseded")


def scope():
    paths = [ROOT / name for name in ROOT_DOCUMENTS]
    paths += sorted((ROOT / "docs").rglob("*.md")) + sorted((ROOT / "docs" / "diagrams").glob("*.mmd"))
    for directory in ("harness", "tools"):
        paths += sorted(p for p in (ROOT / directory).rglob("*")
                        if p.is_file() and p.suffix in (".py", ".mjs", ".js", ".cjs", ".md", ".json")
                        and "node_modules" not in p.parts and "__pycache__" not in p.parts)
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if (not relative.startswith(ALLOWED) and relative not in ALLOWED + GENERATED and current(path)):
            yield relative, path.read_text(encoding="utf-8").splitlines()


def registry_lines():
    """Current control definitions; dated exercises and reviews are preserved evidence."""
    value = json.loads((ROOT / REGISTRY).read_text(encoding="utf-8"))
    for control in value["controls"]:
        current_fields = {key: field for key, field in control.items() if key not in DATED_RECORDS}
        yield f"{REGISTRY} {control['id']}", json.dumps(current_fields, ensure_ascii=False).split("\\n")


def violations():
    found = []
    for relative, lines in [*scope(), *registry_lines()]:
        for number, line in enumerate(lines, 1):
            if PRODUCT.search(CITATIONS.sub("", line)):
                found.append(f"{relative}:{number}: {line.strip()[:160]}")
    return found


def test_current_design_and_tooling_are_host_neutral():
    assert violations() == []


def test_checker_sees_names_but_not_citations_or_lowercase_words():
    assert PRODUCT.search("the generic Pi host") and PRODUCT.search("Codex trust") and PRODUCT.search("Claude Code")
    assert PRODUCT.search("@earendil-works/pi-agent-core")
    assert not PRODUCT.search(CITATIONS.sub("", "[Codex issue](https://github.com/openai/codex/issues/1)"))
    # Internal link text is prose and still checked; only its destination is a path.
    assert PRODUCT.search(CITATIONS.sub("", "[Pi host](../tools/player_host/README.md)"))
    assert not PRODUCT.search("api pid pip spin")


def test_dated_registry_records_are_evidence_but_definitions_are_checked(tmp_path, monkeypatch):
    registry = dict(controls=[dict(id="C-X", mechanism="generic", maintenance_review=dict(cost="Codex usage"),
                                   last_exercise=dict(outcome="Pi run"))])
    (tmp_path / "docs").mkdir()
    (tmp_path / REGISTRY).write_text(json.dumps(registry))
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    assert list(line for _, lines in registry_lines() for line in lines if PRODUCT.search(line)) == []
    registry["controls"][0]["mechanism"] = "Codex rules"
    (tmp_path / REGISTRY).write_text(json.dumps(registry))
    assert any(PRODUCT.search(line) for _, lines in registry_lines() for line in lines)
