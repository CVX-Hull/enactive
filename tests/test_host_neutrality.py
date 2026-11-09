"""Current design, harness and tooling name no specific player host or coding agent.

Only the adapter, setup and operator pages may name them. Historical and superseded
records and external citations are evidence and stay untouched; internal link
destinations are paths, not prose.

Provider and model names are narrower: they stay out of `harness/` and out of `tools/`
outside the host adapters (`tools/player_host/`, `tools/curator_host/`). Documents, research
pages, ADRs, dated records, data and tests may name them (ADR 010).
"""
from pathlib import Path
import re

import frontmatter

ROOT = Path(__file__).resolve().parents[1]
# `pi` as a lowercase word is not a host name; only the capitalized product name is.
PRODUCT = re.compile(r"\bPi\b|pi-player-host|pi-agent-core|pi-ai\b|pi-mcp|earendil|[Cc]odex|CODEX|[Cc]laude|CLAUDE")
# Provider names and model identifiers (`gpt-4o`, `gemini-pro`, the project's `opus` and `terra` arms).
# `claude-…` model ids are already caught by PRODUCT.
PROVIDER = re.compile(r"[Oo]pen[Rr]outer|OPENROUTER|[Aa]nthropic|ANTHROPIC|[Oo]pen[Aa][Ii]|OPENAI|\b[Gg][Pp][Tt]-|\b[Gg]emini\b"
                      r"|\b[Oo]pus\b|\b[Tt]erra\b|\bSonnet\b|\bHaiku\b")
PROVIDER_SCOPE = ("harness/", "tools/")
# An external citation (title and URL), an internal link destination, or a bare URL.
CITATIONS = re.compile(r"\[[^\]]*\]\(https?://[^)]*\)|\]\([^)]*\)|https?://\S+")
ALLOWED = (
    "tools/player_host/",     # current adapter
    "tools/curator_host/",    # the curator's adapter (ADR 009 P0 shadow)
    "docs/operations/",       # operator procedures, including coding-agent hosts
    "docs/setup.md",
    "docs/environment.md",
    "docs/operator-permissions.md",
    "docs/runbook.md",        # operations index
    "NOTICE.md",              # third-party attribution
)
ROOT_DOCUMENTS = ("README.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md", "NOTICE.md")
# The dated-record indexes list the scopes of historical records verbatim.
GENERATED = ("docs/acceptance/index.md", "docs/changes/index.md")


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
                        if p.is_file() and p.suffix in (".py", ".mjs", ".js", ".cjs", ".md", ".json", ".mm", ".cpp", ".h", ".sh")
                        and "node_modules" not in p.parts and "__pycache__" not in p.parts)
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if (not relative.startswith(ALLOWED) and relative not in ALLOWED + GENERATED and current(path)):
            yield relative, path.read_text(encoding="utf-8").splitlines()


def names(relative: str, line: str) -> bool:
    """Whether the line names a host or agent, or (in `harness/` and `tools/`) a provider or model."""
    text = CITATIONS.sub("", line)
    return bool(PRODUCT.search(text) or (relative.startswith(PROVIDER_SCOPE) and PROVIDER.search(text)))


def violations():
    found = []
    for relative, lines in scope():
        for number, line in enumerate(lines, 1):
            if names(relative, line):
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


def test_provider_and_model_names_are_refused_in_harness_and_tools_only():
    for line in ("OPENROUTER = Provider(", "an Anthropic request", "set openai_key", "model='gpt-4o'", "the opus arm",
                 "Opus 4", "GPT-5", "the Terra arm", "Gemini Pro", "gemini-pro", "Sonnet and Haiku"):
        assert names("harness/curator/proxy.py", line) and names("tools/diff_cost.py", line), line
    # Adapters are exempt from the scan itself; documents, research and tests are out of its scope.
    assert not names("docs/research-curated-programs.md", "OpenAI's agent and Anthropic's agent")
    assert not names("tests/test_curator_openrouter.py", "from tools.curator_host.providers import OPENROUTER")
    # Ordinary words and external citations are not names.
    assert not names("harness/curator/proxy.py", "a gptq opusculum terrain terrace route geminian haikus sonnets")
    assert not names("tools/diff_cost.py", "[provider docs](https://openrouter.ai/docs/faq)")
    assert not any(relative.startswith(("tools/curator_host/", "tools/player_host/")) for relative, _ in scope())
