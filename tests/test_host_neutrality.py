"""Current design, harness and tooling name no specific player host or coding agent.

Only the adapter, setup and operator pages may name them. Historical and superseded
records are evidence and stay untouched; link destinations and URLs are citations.
"""
from pathlib import Path
import re

import frontmatter

ROOT = Path(__file__).resolve().parents[1]
NAMES = re.compile(r"\bPi\b|pi-player-host|codex|claude", re.IGNORECASE)
# `pi` as a lowercase word is not a host name; only the capitalized product name is.
PRODUCT = re.compile(r"\bPi\b|pi-player-host|[Cc]odex|CODEX|[Cc]laude|CLAUDE")
CITATIONS = re.compile(r"\]\([^)]*\)|https?://\S+")
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


def current(path: Path) -> bool:
    if path.suffix != ".md":
        return True
    status = frontmatter.loads(path.read_text(encoding="utf-8")).metadata.get("status")
    return status not in ("historical", "superseded")


def scope():
    paths = [ROOT / name for name in ROOT_DOCUMENTS]
    paths += sorted((ROOT / "docs").rglob("*.md")) + sorted((ROOT / "docs" / "diagrams").glob("*.mmd"))
    paths.append(ROOT / "docs" / "control-registry.json")
    for directory in ("harness", "tools"):
        paths += sorted(p for p in (ROOT / directory).rglob("*")
                        if p.is_file() and p.suffix in (".py", ".mjs", ".js", ".cjs", ".md", ".json")
                        and "node_modules" not in p.parts and "__pycache__" not in p.parts)
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if not relative.startswith(ALLOWED) and relative not in ALLOWED and current(path):
            yield relative, path


def violations():
    found = []
    for relative, path in scope():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if PRODUCT.search(CITATIONS.sub("", line)):
                found.append(f"{relative}:{number}: {line.strip()[:160]}")
    return found


def test_current_design_and_tooling_are_host_neutral():
    assert violations() == []


def test_checker_sees_names_but_not_citations_or_lowercase_words(tmp_path):
    assert PRODUCT.search("the generic Pi host") and PRODUCT.search("Codex trust") and PRODUCT.search("Claude Code")
    assert not PRODUCT.search(CITATIONS.sub("", "[issue](https://github.com/openai/codex/issues/1)"))
    assert not PRODUCT.search("api pid pip spin")
    assert NAMES.search("CODEX")
