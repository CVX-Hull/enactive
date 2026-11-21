"""Enforce docs/standards/documentation.md#coding-agents-providers-and-models.

Active and proposed root and docs pages avoid coding-agent, provider and model names.
Operations pages, licence attribution, generated indexes and dated records with historical
or superseded status are exempt. Linked external citations, URLs, internal link destinations,
existing tree paths in inline code and fenced code examples are skipped. Internal link text
and unlinked citations are checked. Owner decision quotes use bracketed descriptions in place
of product names.
The harness and tools scan keeps its own vocabulary and scope outside the host adapters.
"""
from pathlib import Path
import re

import frontmatter
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
# `pi` as a lowercase word is not a host name; only the capitalized product name is.
PRODUCT = re.compile(r"\bPi\b|pi-player-host|pi-agent-core|pi-ai\b|pi-mcp|earendil|[Cc]odex|CODEX|[Cc]laude|CLAUDE")
# Provider names and model identifiers (`gpt-4o`, `gemini-pro`, the project's `opus` and `terra` arms).
# `claude-…` model ids are already caught by PRODUCT.
PROVIDER = re.compile(r"[Oo]pen[Rr]outer|OPENROUTER|[Aa]nthropic|ANTHROPIC|[Oo]pen[Aa][Ii]|OPENAI|\b[Gg][Pp][Tt]-|\b[Gg]emini\b"
                      r"|\b[Oo]pus\b|\b[Tt]erra\b|\bSonnet\b|\bHaiku\b")
PROVIDER_SCOPE = ("harness/", "tools/")
# Document vocabulary comes from the operations pages, delegate config, attempts ledger
# and named models in current research pages.
# Opus and Terra are also used as lowercase arm names. `pro` is a generic tier label.
DOCUMENT_NAMES = re.compile(
    r"\b(?:Antigravity|ANTIGRAVITY|agy|GPT|[Oo]pus|[Tt]erra|Sonnet|Haiku|Fable|Sol|Astra|Luna"
    r"|Neon|Carbon|Argon|Flash|flash_lite|Google|Qwen[0-9]*|Llama|Kimi)\b"
    r"|\b(?i:gpt)-"
    r"|\b(?i:OpenRouter|Anthropic|OpenAI|Gemini|DeepSeek|DeepInfra)(?=\b|_)"
    r"|\b(?:google(?=/)|GOOGLE(?=_API_KEY\b))"
)
# An external citation (title and URL), an internal link destination, or a bare URL.
CITATIONS = re.compile(r"\[[^\]]*\]\(https?://[^)]*\)|\]\([^)]*\)|https?://\S+")
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
EXEMPT_DIRECTORIES = ("tools/player_host/", "tools/curator_host/", "docs/operations/")
EXEMPT_DOCUMENTS = {"NOTICE.md", "docs/acceptance/index.md", "docs/changes/index.md", "docs/decisions/index.md"}
MARKDOWN = MarkdownIt("commonmark").enable("table")


def scope():
    paths = [*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md")]
    for directory in ("harness", "tools"):
        paths.extend(p for p in (ROOT / directory).rglob("*")
                     if p.is_file() and p.suffix in (".py", ".mjs", ".js", ".cjs", ".md", ".json", ".mm", ".cpp", ".h", ".sh")
                     and "node_modules" not in p.parts and "__pycache__" not in p.parts)
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(EXEMPT_DIRECTORIES) or relative in EXEMPT_DOCUMENTS:
            continue
        source = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            status = frontmatter.loads(source).metadata.get("status")
            if relative.startswith(PROVIDER_SCOPE):
                if status in ("historical", "superseded"):
                    continue
            elif status not in ("active", "proposed"):
                continue
        yield relative, source


def names(relative: str, line: str) -> bool:
    """Whether the line names a coding agent, player host, provider or model."""
    if relative.startswith(PROVIDER_SCOPE):
        text = CITATIONS.sub("", line)
        return bool(PRODUCT.search(text) or PROVIDER.search(text))

    text = CITATIONS.sub(" ", line)
    if relative.startswith("docs/") or ("/" not in relative and relative.endswith(".md")):
        def omit_tree_path(match: re.Match[str]) -> str:
            path_text = re.sub(r":\d+$", "", match[2].strip()).rstrip("/")
            candidate = Path(path_text)
            if path_text and not candidate.is_absolute():
                for directory in (ROOT, (ROOT / relative).parent):
                    path = directory / candidate
                    if path.exists() and path.resolve().is_relative_to(ROOT):
                        return " "
            return match[0]

        text = INLINE_CODE.sub(omit_tree_path, text)
        return bool(PRODUCT.search(text) or DOCUMENT_NAMES.search(text))
    return bool(PRODUCT.search(text))


def violations():
    found = []
    for relative, source in scope():
        fenced = set()
        if not relative.startswith(PROVIDER_SCOPE):
            fenced = {number for token in MARKDOWN.parse(source) if token.type == "fence"
                      for number in range(*token.map)}
        for number, line in enumerate(source.splitlines(), 1):
            if number - 1 not in fenced and names(relative, line):
                found.append(f"{relative}:{number}: {line}")
    return found


def test_current_guidance_and_tooling_are_host_neutral():
    assert violations() == []


def test_the_scan_covers_code_and_current_guidance():
    scanned = {relative for relative, _ in scope()}
    assert {"AGENTS.md", "docs/architecture.md", "docs/contracts/player-host.md",
            "docs/design/player-context.md", "docs/setup.md", "docs/environment.md",
            "docs/operator-permissions.md", "docs/runbook.md",
            "harness/player_tools.py", "tools/check.py"} <= scanned


def test_documents_match_product_provider_and_model_names():
    for line in ("the Pi host", "Codex trust", "Claude Code", "@earendil-works/pi-agent-core",
                 "Antigravity", "`agy --version`", "OpenRouter", "Anthropic", "OpenAI", "Google's model",
                 "DeepSeek", "DeepInfra", "GPT-5", "gpt-6.2-sol", "Gemini", "gemini-4-neon", "Opus",
                 "Sonnet", "Haiku", "Fable", "Terra", "the terra arm", "Sol", "Astra", "Luna",
                 "Neon", "Carbon", "Argon", "Flash", "flash_lite", "Qwen3-30B-A3B", "Llama", "Kimi",
                 "`OPENROUTER_API_KEY`"):
        assert names("docs/design/player-context.md", line), line
        assert names("docs/setup.md", line), line


def test_document_line_distinguishes_prose_citations_destinations_and_inline_code():
    relative = "docs/setup.md"
    assert not names(relative, "[Codex issue](https://github.com/openai/codex/issues/1)")
    assert not names(relative, "See <https://openrouter.ai/docs/faq>.")
    assert not names(relative, "[Setup](./Codex.md)")
    assert not names(relative, "Use `tools/player_host/` and `CLAUDE.md:2`.")
    assert not names(relative, "See `tools/player_host/:12`.")
    assert not names(relative, "Use ``../tools/player_host/``.")
    assert names(relative, "[Pi host](../tools/player_host/README.md)")
    assert names(relative, "Run `claude -p`.")
    assert names(relative, "The path `missing/Codex.md` does not exist.")
    assert names(relative, "Source: Anthropic, Writing effective tools.")
    assert not names(relative, "sun astral terrace opusculum haikus sonnets pid api pip spin neon light carbon pro")
    assert not names(relative, "strategy neopencarbon preOpenAI")


def test_document_scan_skips_fences_and_exempt_pages(tmp_path, monkeypatch):
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    for relative, status in (
        ("NOTICE.md", "active"),
        ("docs/operations/host.md", "active"),
        ("docs/acceptance/index.md", "active"),
        ("docs/changes/index.md", "active"),
        ("docs/decisions/index.md", "active"),
        ("docs/design/history.md", "historical"),
        ("docs/design/replaced.md", "superseded"),
        ("docs/design/no-status.md", ""),
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nstatus: {status}\n---\nCodex\n", encoding="utf-8")

    design = tmp_path / "docs/design/current.md"
    design.write_text(
        "---\nstatus: proposed\n---\n\nClaude Code\n\n"
        "````Codex\nOpenAI\n```\nDeepSeek\n````\n"
        "~~~Gemini\nAstra\n~~~\n\nOpenRouter\n",
        encoding="utf-8",
    )
    setup = tmp_path / "docs/setup.md"
    setup.write_text("---\nstatus: active\n---\n\nAntigravity\n", encoding="utf-8")

    assert violations() == [
        "docs/design/current.md:5: Claude Code",
        "docs/design/current.md:16: OpenRouter",
        "docs/setup.md:5: Antigravity",
    ]


def test_harness_and_tools_keep_their_provider_and_model_vocabulary():
    for line in ("OPENROUTER = Provider(", "an Anthropic request", "set openai_key", "model='gpt-4o'", "the opus arm",
                 "Opus 4", "GPT-5", "the Terra arm", "Gemini Pro", "gemini-pro", "Sonnet and Haiku"):
        assert names("harness/curator/proxy.py", line) and names("tools/diff_cost.py", line), line
    assert not names("harness/curator/proxy.py", "Antigravity agy DeepSeek Fable Sol Astra")
    assert names("tools/example.md", "`CLAUDE.md`")
    assert not names("tests/test_curator_openrouter.py", "from tools.curator_host.providers import OPENROUTER")
    # Ordinary words and external citations are not names.
    assert not names("harness/curator/proxy.py", "a gptq opusculum terrain terrace route geminian haikus sonnets")
    assert not names("tools/diff_cost.py", "[provider docs](https://openrouter.ai/docs/faq)")
    assert not any(relative.startswith(("tools/curator_host/", "tools/player_host/")) for relative, _ in scope())
