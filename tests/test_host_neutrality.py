"""Check the naming rule in docs/standards/documentation.md#coding-agents-providers-and-models.

Current pages outside operations avoid coding-agent, provider, model and player-host
names, subject to the rule's limits. The harness and tools source scan retains its
own vocabulary and host-adapter exclusions.
"""

from collections import defaultdict
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import frontmatter
from markdown_it import MarkdownIt
import pytest

from tools.documents import EARLIER_RECORD_KINDS, INDEXES, NEW_RECORD_KINDS, render_index

ROOT = Path(__file__).resolve().parents[1]
# Keep the harness and tools vocabulary and exclusions independent of the page rule.
PRODUCT = re.compile(r"\bPi\b|pi-player-host|pi-agent-core|pi-ai\b|pi-mcp|earendil|[Cc]odex|CODEX|[Cc]laude|CLAUDE")
PROVIDER = re.compile(r"[Oo]pen[Rr]outer|OPENROUTER|[Aa]nthropic|ANTHROPIC|[Oo]pen[Aa][Ii]|OPENAI|\b[Gg][Pp][Tt]-|\b[Gg]emini\b"
                      r"|\b[Oo]pus\b|\b[Tt]erra\b|\bSonnet\b|\bHaiku\b")
CITATIONS = re.compile(r"\[[^\]]*\]\(https?://[^)]*\)|\]\([^)]*\)|https?://\S+")
SOURCE_ADAPTERS = ("tools/player_host/", "tools/curator_host/")
SOURCE_SUFFIXES = {".py", ".mjs", ".js", ".cjs", ".md", ".json", ".mm", ".cpp", ".h", ".sh"}

# Page vocabulary comes from the supported hosts and routes, model-routing guide and
# research. Underscores delimit names in constants. Common words keep product case
# or require model context, such as a version or a named comparison arm.
AGENT = re.compile(
    r"(?<![A-Za-z0-9])(?:(?i:Claude|agy)|Codex|CODEX|Antigravity|ANTIGRAVITY)(?![A-Za-z0-9])"
    r"|\bcodex(?=\s+(?:exec|review|resume)\b)"
)
PLAYER_HOST = re.compile(
    r"(?<![A-Za-z0-9])(?:Pi(?=\d+\.\d+|[^A-Za-z0-9]|$)|PI(?=_)"
    r"|(?i:earendil|pi-player-host|pi-agent-core|pi-ai|pi-mcp)(?![A-Za-z0-9]))"
)
ADAPTER_ROUTE = re.compile(
    r"(?<![A-Za-z0-9])(?i:OpenAI|OpenRouter|DeepInfra|Baseten)(?![A-Za-z0-9])"
)
PROVIDER_OR_MODEL = re.compile(
    r"(?<![A-Za-z0-9])(?:(?i:OpenRouter|Anthropic|OpenAI|DeepSeek|DeepInfra|Baseten"
    r"|Google|Gemini|GPT|Qwen\d*|Kimi|flash_lite)"
    r"|Opus|Terra|Sonnet|Haiku|Fable|Sol|Astra|Luna|Neon|Carbon|Argon|Flash|Llama)(?![A-Za-z0-9])"
    r"|\b(?:opus|terra)(?=\s+(?:\d|arm\b))"
)
PLAYER_ADAPTER = "tools/player_host/README.md"
LICENCE_TEXT = {"NOTICE.md", "LICENSE", "LICENSE-CDDA.txt", "web/vendor/LICENSE-echarts",
                "web/vendor/LICENSE-preact", "web/vendor/LICENSE-htm", "web/vendor/NOTICE-echarts"}
MARKDOWN = MarkdownIt("commonmark").enable("table")
WEB_URL = re.compile(r'https?://[^\s<>\])]+', re.IGNORECASE)
SOURCE_ID = re.compile(r"\b[A-Z]\d+\b")
ARXIV_ID = re.compile(
    r"\barXiv\s*:?\s*(?:\d{4}\.\d{4,5}|[a-z.-]+/\d{7})(?:v\d+)?\b"
    r"|\b\d{2}(?:0[1-9]|1[0-2])\.\d{4,5}v\d+\b", re.IGNORECASE,
)
SOURCE_COLUMN = re.compile(r"(?:primary |outside |external )?sources?(?:\s*/.*|\s+and .*|\s*\(.*\))?", re.IGNORECASE)
LITERAL = r"[\w.-]+(?:[/:][\w.-]+)*"
QUOTED_IDENTIFIER = re.compile(rf"""(["'`])({LITERAL})\1""")
BARE_IDENTIFIER = re.compile(rf"(?<![\w./:-]){LITERAL}(?=\s*(?:[=:,{{}}\[\]()]|$))")
LITERAL_LINE = re.compile(rf"\s*(?:{LITERAL}\s*,?\s*$|{LITERAL}\s*[=:]|{LITERAL}\(|[{{\[\]}}]|-\s+)")
SCHEMA_EXAMPLE = re.compile(r"\b(?:schema examples?|examples? of the schema)\b", re.IGNORECASE)


def source_scope():
    for directory in ("harness", "tools"):
        for path in sorted((ROOT / directory).rglob("*")):
            relative = path.relative_to(ROOT).as_posix()
            if (path.suffix not in SOURCE_SUFFIXES or not path.is_file()
                    or relative.startswith(SOURCE_ADAPTERS)
                    or "node_modules" in path.parts or "__pycache__" in path.parts):
                continue
            source = path.read_text(encoding="utf-8")
            if path.suffix == ".md" and frontmatter.loads(source).get("status") in ("historical", "superseded"):
                continue
            yield relative, source


def source_names(line):
    text = CITATIONS.sub("", line)
    return PRODUCT.search(text) or PROVIDER.search(text)


def page_scope():
    # Project caches, dependencies and secondary worktrees are outside the source tree.
    excluded = {".git", ".runtime", ".cache", ".venv", ".pytest_cache", "worktrees", "node_modules", "__pycache__"}
    for directory, dirs, files in ROOT.walk():
        dirs[:] = sorted(set(dirs) - excluded)
        for name in sorted(files):
            relative = (directory / name).relative_to(ROOT).as_posix()
            if name.endswith(".md") and not relative.startswith("docs/operations/"):
                yield relative, (directory / name).read_text(encoding="utf-8")


def tree_path(relative, target, *, link=False):
    if link:
        url = urlsplit(target)
        if url.scheme or url.netloc:
            return False
        if not url.path:
            return True  # A same-page link carries only a fragment.
        target = unquote(url.path)
    else:
        target = re.sub(r":\d+$", "", target)
        if target.startswith("/"):
            return False
    target = target.rstrip("/")
    if target.startswith("/"):
        bases = (ROOT,)
    elif link:
        bases = ((ROOT / relative).parent,)
    else:
        bases = ((ROOT / relative).parent, ROOT)
    for base in bases:
        path = base / target.lstrip("/")
        if path.exists() and path.resolve().is_relative_to(ROOT):
            return True
    return False


def outside_url(target):
    url = urlsplit(target)
    if url.scheme not in ("http", "https") or not url.netloc:
        return False
    if url.hostname == "github.com":
        path = url.path.lower().rstrip("/")
        if (path == "/cvx-hull/enactive" or path.startswith("/cvx-hull/enactive/")
                or path.startswith("/users/cvx-hull/projects/")):
            return False
    return True


def citation_lines(tokens):
    """Mark source rows and the paragraphs or list items that cite an outside source."""
    source_ids = set()
    cited = set()
    table_rows = defaultdict(list)
    inlines = defaultdict(list)
    items = []
    table = None
    for token in tokens:
        if token.type == "table_open":
            table = token.map[0]
        elif token.type == "table_close":
            table = None
        elif token.type == "list_item_open":
            items.append(token.map[0])
        elif token.type == "list_item_close":
            items.pop()
        elif token.type == "inline":
            start, end = token.map
            if table is not None:
                table_rows[start].append(token.content)
                cells = table_rows[table]
                if start != table and (
                    SOURCE_COLUMN.fullmatch(cells[0]) or
                    (len(cells) >= 2 and cells[0].lower() == "id" and SOURCE_COLUMN.fullmatch(cells[1]))
                ):
                    cited.add(start)
                    source_id = table_rows[start][0]
                    if SOURCE_ID.fullmatch(source_id):
                        source_ids.add(source_id)
            group = ("item", items[-1]) if items and table is None else ("line", start)
            inlines[group].append((start, end, token.children))

    for blocks in inlines.values():
        # A source key has to be defined in the page. URLs in inline code are literals.
        children = [child for _, _, children in blocks for child in children]
        references = [child.content for child in children if child.type in ("text", "code_inline")]
        if (any(outside_url(child.attrGet("href")) for child in children if child.type == "link_open")
                or any(outside_url(match[0]) for child in children if child.type == "text"
                       for match in WEB_URL.finditer(child.content))
                or any(ARXIV_ID.search(value) or source_ids.intersection(SOURCE_ID.findall(value))
                       for value in references)):
            for start, end, _ in blocks:
                cited.update(range(start, end))
    return cited


def fence_text(line):
    """Remove literal tokens in code, retaining prose, including comments and strings."""
    code, hash_comment, comment = line.partition(" #")
    code, separator, trailing = code.partition(" //")
    literals = QUOTED_IDENTIFIER.sub("_", code)
    # Assignments, calls and structured values can carry literal identifiers.
    # Free text, including multi-word strings and comments, stays checked.
    if not LITERAL_LINE.match(literals):
        return line
    parts = re.split(r'''("[^"]*"|'[^']*')''', literals)
    return "".join(BARE_IDENTIFIER.sub(" ", part) if index % 2 == 0 else part
                   for index, part in enumerate(parts)) + separator + trailing + hash_comment + comment


def page_text(relative, line, env, *, schema_example=False):
    """Read the visible inline text, retaining unresolved file names for the check."""
    parts = []
    for token in MARKDOWN.parseInline(line, env)[0].children:
        if token.type == "link_open":
            target = token.attrGet("href")
            if not WEB_URL.fullmatch(target) and not tree_path(relative, target, link=True):
                parts.append(urlsplit(target).path)
        elif token.type == "text":
            parts.append(WEB_URL.sub(" ", token.content))
        elif token.type == "code_inline":
            if not tree_path(relative, token.content):
                literal = token.content
                if literal in ("codex", "antigravity"):
                    literal = literal.capitalize()
                parts.append(fence_text(literal) if schema_example else literal)
        elif token.type in ("image", "html_inline"):
            parts.append(token.content)
    return " ".join(parts)


def page_violations(relative, source):
    if relative.startswith("docs/operations/") or relative in LICENCE_TEXT:
        return []
    metadata = frontmatter.loads(source).metadata
    if metadata.get("status") not in ("active", "proposed"):
        return []
    if (relative.startswith("docs/acceptance/") and metadata.get("date")
            and metadata.get("kind") in NEW_RECORD_KINDS + EARLIER_RECORD_KINDS):
        return []

    # Only rows reproduced by the generator get its limit. The documents check
    # independently reports drift between the index and its records.
    reproduced = set()
    if relative in INDEXES:
        reproduced = {line for line in render_index(ROOT, relative).splitlines() if line.startswith("| ")}
    env = {}
    tokens = MARKDOWN.parse(source, env)
    lines = source.splitlines()
    cited = citation_lines(tokens)
    fences = {number for token in tokens if token.type == "fence" for number in range(*token.map)}
    schema_examples = set()
    specification = relative.startswith("docs/contracts/")
    if specification:
        headings = [token for token in tokens if token.type == "heading_open"]
        for index, heading in enumerate(headings):
            if SCHEMA_EXAMPLE.search(lines[heading.map[0]]):
                end = headings[index + 1].map[0] if index + 1 < len(headings) else len(lines)
                schema_examples.update(range(heading.map[1], end))

    found = []
    adapter = relative == PLAYER_ADAPTER
    for index, line in enumerate(lines):
        if line in reproduced:
            continue
        text = line if index in fences else page_text(relative, line, env)
        if not adapter and PLAYER_HOST.search(text):
            found.append(f"{relative}:{index + 1}: {line}")
            continue
        if index in cited:
            continue
        if index in fences and specification:
            text = fence_text(text)
        elif index in schema_examples:
            text = page_text(relative, line, env, schema_example=True)
        if adapter:
            text = ADAPTER_ROUTE.sub(" ", text)
        if AGENT.search(text) or PROVIDER_OR_MODEL.search(text):
            found.append(f"{relative}:{index + 1}: {line}")
    return found


def violations():
    found = [hit for relative, source in page_scope() for hit in page_violations(relative, source)]
    for relative, source in source_scope():
        for number, line in enumerate(source.splitlines(), 1):
            if source_names(line):
                hit = f"{relative}:{number}: {line}"
                if hit not in found:
                    found.append(hit)
    return found


def test_current_guidance_and_tooling_are_host_neutral():
    assert violations() == []


def test_the_scan_covers_code_and_current_guidance():
    assert {"AGENTS.md", "docs/architecture.md", "docs/contracts/player-host.md",
            "docs/design/curator-memory-study-protocol-revised.md", "docs/setup.md",
            "docs/environment.md", "docs/operator-permissions.md", "docs/runbook.md",
            PLAYER_ADAPTER} <= {relative for relative, _ in page_scope()}
    scanned = {relative for relative, _ in source_scope()}
    assert {"harness/player_tools.py", "tools/check.py"} <= scanned
    assert not any(relative.startswith(SOURCE_ADAPTERS) for relative in scanned)


def test_harness_and_tools_keep_their_provider_and_model_vocabulary():
    for line in ("OPENROUTER = Provider(", "an Anthropic request", "set openai_key", "model='gpt-4o'", "the opus arm",
                 "Opus 4", "GPT-5", "the Terra arm", "Gemini Pro", "gemini-pro", "Sonnet and Haiku", "`CLAUDE.md`"):
        assert source_names(line), line
    assert not source_names("Antigravity agy DeepSeek Fable Sol Astra")
    assert not source_names("a gptq opusculum terrain terrace route geminian haikus sonnets")
    assert not source_names("[provider docs](https://openrouter.ai/docs/faq)")


def current_page(body):
    return "---\nstatus: active\n---\n\n" + body


def test_pages_match_the_supported_hosts_providers_and_models():
    names = (
        "Codex", "codex exec", "`codex`", "Claude Code", "Antigravity", "`agy --version`",
        "Pi", "Pi1.4.0", "pi-player-host", "pi-agent-core", "pi-ai", "pi-mcp", "earendil",
        "OpenAI", "Anthropic", "Google", "OpenRouter", "DeepSeek", "DeepInfra", "Baseten",
        "GPT-5", "gpt-6.2-sol", "Gemini", "Opus", "Sonnet", "Haiku", "Fable", "Terra", "Sol",
        "Astra", "Luna", "Neon", "Carbon", "Argon", "Flash", "flash_lite", "Qwen3-30B-A3B",
        "Llama", "Kimi", "the terra arm", "opus 4", "`OPENROUTER_API_KEY`",
    )
    for name in names:
        assert page_violations("docs/setup.md", current_page(name)) == [f"docs/setup.md:5: {name}"]

    ordinary = "pi, a medieval codex, antigravity, a literary opus, a haiku, a fable, carbon, neon and a flash."
    assert page_violations("docs/setup.md", current_page(ordinary)) == []


@pytest.mark.parametrize("status", ("historical", "superseded", "active", "proposed", ""))
def test_only_current_statuses_are_checked(status):
    path = "docs/design/current.md"
    assert page_violations(path, f"---\nstatus: {status}\n---\n\nCodex") == (
        [f"{path}:5: Codex"] if status in ("active", "proposed") else []
    )


def test_a_dated_record_is_exempt_but_a_date_does_not_exempt_current_guidance():
    page = "---\nstatus: active\nkind: review\ndate: 2026-11-21\n---\n\nCodex"
    assert page_violations("docs/acceptance/2026-11-21-review.md", page) == []
    assert page_violations("docs/design/current.md", page) == ["docs/design/current.md:7: Codex"]


def test_only_reproduced_index_rows_are_exempt(tmp_path, monkeypatch):
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    record = tmp_path / "docs/acceptance/2026-11-21-review.md"
    record.parent.mkdir(parents=True)
    record.write_text("---\nstatus: historical\ndate: 2026-11-21\n---\n\n# Codex trial\n")
    relative = "docs/acceptance/index.md"
    generated = render_index(tmp_path, relative)
    page = f"{generated}\nCodex trial\n"
    assert page_violations(relative, page) == [f"{relative}:{len(page.splitlines())}: Codex trial"]


def test_operations_and_licence_attribution_allow_names():
    body = current_page("Pi, Codex, OpenAI and GPT-5")
    for path in ("NOTICE.md", "LICENSE-CDDA.txt", "docs/operations/hosts.md"):
        assert page_violations(path, body) == []
    assert page_violations("docs/setup.md", body) == ["docs/setup.md:5: Pi, Codex, OpenAI and GPT-5"]


def test_the_player_adapter_can_name_its_host_and_route():
    body = current_page("Pi uses OpenRouter via DeepInfra.\n\nUse Anthropic or Claude Code.")
    assert page_violations(PLAYER_ADAPTER, body) == [
        f"{PLAYER_ADAPTER}:7: Use Anthropic or Claude Code."
    ]
    assert page_violations("docs/setup.md", current_page("Pi uses OpenRouter via DeepInfra."))


def test_outside_citations_are_limited_to_their_block_or_source_row():
    relative = "docs/research-example.md"
    body = current_page("""| ID | Source |
| --- | --- |
| S12 | OpenAI, study results |
| S13 | Anthropic, study methods |

| Setting | Finding |
| --- | --- |
| Project default | OpenAI |

- The study (S12) compared
  OpenAI and Anthropic.

  The cited result also used Claude Code.
  - A related project should use Anthropic.

- Use Anthropic for new project work (S99).

The test used Codex
and has a [reference link][paper].

The paper used Gemini (arXiv: 2601.01234v2).

GPT-5 was evaluated in 2601.01234v2.

[Anthropic's paper](https://example.org/study) describes the result for Pi.

Use Gemini locally ([project issue](https://github.com/CVX-Hull/enactive/issues/873)).

Use Codex locally.

[paper]: https://example.org/study
""")
    expected = (
        "| Project default | OpenAI |",
        "  - A related project should use Anthropic.",
        "- Use Anthropic for new project work (S99).",
        "[Anthropic's paper](https://example.org/study) describes the result for Pi.",
        "Use Gemini locally ([project issue](https://github.com/CVX-Hull/enactive/issues/873)).",
        "Use Codex locally.",
    )
    assert page_violations(relative, body) == [
        f"{relative}:{body.splitlines().index(line) + 1}: {line}" for line in expected
    ]


def test_only_existing_tree_paths_are_exempt(tmp_path, monkeypatch):
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "Codex.md").touch()
    (tmp_path / "OpenAI").mkdir()
    relative = "docs/setup.md"
    body = current_page("""Use `Codex.md:2` and ``../OpenAI/``.
See [setup](../Codex.md#claude-code).
[OpenAI](../Codex.md) is the default.
Use `OpenAI/missing.json`.
See [setup](../missing/Codex.md).
""")
    assert page_violations(relative, body) == [
        f"{relative}:7: [OpenAI](../Codex.md) is the default.",
        f"{relative}:8: Use `OpenAI/missing.json`.",
        f"{relative}:9: See [setup](../missing/Codex.md).",
    ]


def test_specifications_allow_literal_identifiers_in_fences_and_schema_examples():
    relative = "docs/contracts/example.md"
    body = current_page('''## Schema example

`{"provider": "OpenAI"}`

Use OpenAI.

~~~json
{"provider": "OpenAI", "model": "gpt-5"}
{"note": "Use OpenAI."}
# Use OpenAI.
Use "OpenAI" locally.
{"host": "Pi"}
~~~

## Selection

`{"provider": "OpenAI"}`

~~~text
Provider: OpenAI is active here.
~~~
''')
    assert page_violations(relative, body) == [
        f"{relative}:9: Use OpenAI.",
        f'{relative}:13: {{"note": "Use OpenAI."}}',
        f"{relative}:14: # Use OpenAI.",
        f'{relative}:15: Use "OpenAI" locally.',
        f'{relative}:16: {{"host": "Pi"}}',
        f'{relative}:21: `{{"provider": "OpenAI"}}`',
        f'{relative}:24: Provider: OpenAI is active here.',
    ]
    guidance = current_page('~~~json\n{"provider": "OpenAI"}\n~~~\n')
    assert page_violations("docs/setup.md", guidance) == [
        'docs/setup.md:6: {"provider": "OpenAI"}',
    ]


@pytest.mark.parametrize("relative", ("docs/decisions/owner-decisions.md",
                                      "docs/decisions/owner-decisions-archive.md"))
def test_owner_log_bracketed_descriptions_pass_the_normal_page_scan(relative):
    assert page_violations(relative, current_page('“Use [the lead’s coding agent].”')) == []
    assert page_violations(relative, current_page('“Use Codex.”')) == [f'{relative}:5: “Use Codex.”']
