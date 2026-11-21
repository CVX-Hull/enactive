"""Check the naming rule in docs/standards/documentation.md#coding-agents-providers-and-models.

The page scan checks a fixed vocabulary within the rule's limits. The harness and
tools source scan retains its own vocabulary and host-adapter exclusions.
"""

from collections import defaultdict
from contextlib import contextmanager
from html import unescape
from itertools import chain, pairwise
from pathlib import Path
from posixpath import normpath
import re
import subprocess
import tempfile
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

import frontmatter
from markdown_it import MarkdownIt
import pytest

from tools.documents import EARLIER_RECORD_KINDS, INDEXES, NEW_RECORD_KINDS, render_index

ROOT = Path(__file__).resolve().parents[1]
GIT = ("git", "-c", "core.ignorecase=false")
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
    r"(?<![A-Za-z0-9])(?:Codex|CODEX|(?i:Claude(?:Code|CLI)?|agy(?:CLI)?|Antigravity(?:CLI)?|CodexCLI))"
    r"(?![A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])codex(?=_|-(?!like\b)[A-Za-z0-9]|\s+(?:v?\d|--?"
    r"|(?i:apply|app|app-server|cli|cloud|command|completion|debug|doctor|exec"
    r"|execpolicy|features|fork|help|login|logout|mcp|mcp-server|plugin|resume|review|sandbox|update)\b))"
    r"|(?<=_)codex(?![A-Za-z0-9])"
    r"|\b(?:npx|install)(?:[ \t]+--?[\w-]+)*[ \t]+codex(?![A-Za-z0-9])"
)
PLAYER_HOST = re.compile(
    r"(?<![A-Za-z0-9])(?:Pi(?=\d+\.\d+|[^A-Za-z0-9]|$)|PI(?=_)"
    r"|(?i:earendil|pi-player-host|pi-agent-core|pi-ai|pi-mcp)(?![A-Za-z0-9]))"
)
ADAPTER_ROUTE = re.compile(
    r"(?<![A-Za-z0-9])(?i:OpenAI|OpenRouter|DeepInfra|Baseten)(?![A-Za-z0-9])"
)
MODEL_TIERS = r"Opus|Terra|Sonnet|Haiku|Fable|Sol|Astra|Luna|Neon|Carbon|Argon|Flash|Llama"
PROVIDER_OR_MODEL = re.compile(
    r"(?<![A-Za-z0-9])(?:(?i:OpenRouter|Anthropic|OpenAI|DeepSeek|DeepInfra|Baseten"
    rf"|Google|Gemini|GPT|Qwen\d*|Kimi|flash_lite)|{MODEL_TIERS})(?![A-Za-z0-9])"
    rf"|(?i:(?<![A-Za-z0-9])(?:{MODEL_TIERS})(?=\s*\d|\s+(?:arm|model|tier)\b|-[A-Za-z0-9])"
    rf"|(?<=[A-Za-z0-9]-)(?:{MODEL_TIERS})(?![A-Za-z0-9]))"
)
PLAYER_ADAPTER = "tools/player_host/README.md"
LICENCE_TEXT = {"NOTICE.md", "LICENSE", "LICENSE-CDDA.txt", "web/vendor/LICENSE-echarts",
                "web/vendor/LICENSE-preact", "web/vendor/LICENSE-htm", "web/vendor/NOTICE-echarts"}
MARKDOWN = MarkdownIt("commonmark").enable("table")
WEB_URL = re.compile(r'https?://[^\s<>\])]+', re.IGNORECASE)
HTML_LINK = re.compile(r"""<a\s[^>]*?(?<!\S)href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)
HTML_LINK_CLOSE = re.compile(r"</a\s*>", re.IGNORECASE)
FIRST_PARTY_DOMAINS = (
    "openai.com", "openai.github.io", "chatgpt.com", "anthropic.com", "claude.ai", "claude.com", "google.com", "google.dev",
    "google", "googleapis.com", "googleblog.com", "google.github.io", "openrouter.ai", "deepinfra.com",
    "deepseek.com", "baseten.co", "qwen.ai", "kimi.com", "moonshot.ai", "llama.com", "meta.com",
)
FIRST_PARTY_GITHUB_OWNERS = {
    "openai", "anthropics", "anthropic-experimental", "google", "google-deepmind", "google-gemini", "meta-llama",
    "deepseek-ai", "qwenlm", "moonshotai", "openrouterteam", "deepinfra", "basetenlabs",
}
FIRST_PARTY_HUGGING_FACE_OWNERS = {
    "openai", "anthropic", "google", "google-deepmind", "meta-llama", "facebook", "deepseek-ai",
    "qwen", "moonshotai", "openrouter", "deepinfra", "baseten",
}
CITATION_LINK = "\x00"
SOURCE_ID = re.compile(r"\b[A-Z]\d+\b")
ARXIV_ID = re.compile(
    r"\barXiv\s*:?\s*(?:\d{4}\.\d{4,5}|[a-z.-]+/\d{7})(?:v\d+)?\b"
    r"|\b\d{2}(?:0[1-9]|1[0-2])\.\d{4,5}(?:v\d+)?\b", re.IGNORECASE,
)
SOURCE_COLUMN = re.compile(
    r"(?:primary |outside |external )?sources?(?:\s+(?:keys?|ids?)|\s*/.*|\s+and .*|\s*\(.*\))?",
    re.IGNORECASE,
)
SENTENCE_END = re.compile(r"""([.!?]+)["'”’\])]*(?=\s|$)""")
SENTENCE_ABBREVIATION = re.compile(r"\b(?:[A-Z]|(?i:et al|e\.g|i\.e|cf|fig|vs))$")
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


def tracked_paths(root, *pathspecs):
    output = subprocess.check_output([*GIT, "ls-files", "--deduplicate", "-z", "--", *pathspecs],
                                     cwd=root, text=True)
    return output.split("\0")[:-1]


def page_scope():
    for relative in tracked_paths(ROOT, "*.md"):
        path = ROOT / relative
        if not relative.startswith("docs/operations/") and path.is_file():
            yield relative, path.read_text(encoding="utf-8")


@contextmanager
def git_tree_paths(root):
    tracked = tracked_paths(root)
    paths = {path.as_posix() for name in tracked for path in (Path(name), *Path(name).parents)}
    # Use Git's ignore matcher with only the versioned ignore files. The empty
    # checkout keeps ignored files, local excludes and worktree layout out of it.
    with TemporaryDirectory(prefix="name-check-") as scratch:
        subprocess.run([*GIT, "init", "-q", "--template="], cwd=scratch, check=True)
        for name in tracked:
            if Path(name).name == ".gitignore":
                target = Path(scratch) / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((root / name).read_bytes())
        checked = set()
        ignored = set()

        def match(candidates):
            missing = candidates - paths - checked
            if missing:
                # Anchor paths with ./ so a leading colon stays literal. Check
                # the directory spelling too, even if the directory is absent.
                result = subprocess.run(
                    [*GIT, "-c", "core.excludesFile=/dev/null", "check-ignore", "--no-index", "-z", "--stdin"],
                    cwd=scratch, input="".join(f"./{path}\0./{path}/\0" for path in sorted(missing)),
                    capture_output=True, text=True,
                )
                if result.returncode not in (0, 1):
                    result.check_returncode()
                ignored.update(path.removeprefix("./").rstrip("/") for path in result.stdout.split("\0") if path)
                checked.update(missing)
            return (candidates & paths) | (candidates & ignored)

        yield match


def tree_candidates(relative, target, *, link=False):
    if link:
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
            return
        target = unquote(url.path)
    else:
        target = re.sub(r":\d+$", "", target)
        if target.startswith("/"):
            return
    bases = (Path(relative).parent,) if link else (Path(relative).parent, Path("."))
    if target.startswith("/"):
        bases = (Path("."),)
    for base in bases:
        path = normpath((base / target.lstrip("/")).as_posix())
        if path != ".." and not path.startswith("../"):
            yield path


def inline_paths(relative, inlines):
    for tokens in inlines:
        for token in tokens:
            if token.type == "link_open":
                yield from tree_candidates(relative, token.attrGet("href"), link=True)
            elif token.type == "code_inline":
                yield from tree_candidates(relative, token.content)


def web_link_text(target):
    """Represent a web link by its citation marker or a space for provider sites."""
    url = urlsplit(target)
    if url.scheme not in ("", "http", "https") or not url.hostname:
        return None
    host = url.hostname.rstrip(".")
    path = url.path.lower().rstrip("/")
    if host == "github.com" and (path == "/cvx-hull/enactive" or path.startswith(
            ("/cvx-hull/enactive/", "/users/cvx-hull/projects/"))):
        return None
    if any(host == domain or host.endswith("." + domain) for domain in FIRST_PARTY_DOMAINS):
        return " "
    owner = path.removeprefix("/").partition("/")[0]
    if ((host == "github.com" and owner in FIRST_PARTY_GITHUB_OWNERS)
            or (host == "huggingface.co" and owner in FIRST_PARTY_HUGGING_FACE_OWNERS)):
        return " "
    return CITATION_LINK


def citation_context(tokens):
    """Collect source rows with identifiers, paragraph spans and table cells."""
    source_ids = set()
    source_rows = set()
    paragraphs = []
    cells = defaultdict(list)
    table_header = None
    source_table = False
    for token in tokens:
        if token.type == "table_open":
            table_header = token.map[0]
        elif token.type == "table_close":
            table_header = None
        elif token.type == "thead_close":
            source_table = any(SOURCE_COLUMN.fullmatch(source_cell_text(cell)) for cell in cells[table_header])
        elif token.type == "paragraph_open":
            paragraphs.append(token.map)
        elif token.type == "inline" and table_header is not None:
            start = token.map[0]
            if start != table_header and source_table and not cells[start]:
                source_id = source_cell_text(token)
                if SOURCE_ID.fullmatch(source_id):
                    source_ids.add(source_id)
                    source_rows.add(start)
                elif ARXIV_ID.search(source_id):
                    source_rows.add(start)
            cells[start].append(token)
    return source_ids, source_rows, paragraphs, cells


def source_cell_text(cell):
    return "".join(child.content for child in cell.children if child.type in ("text", "code_inline")).strip()


def uncited_text(text, source_ids, *, table_cell=False):
    """Blank cited sentences while preserving physical line breaks."""
    boundaries = [0]
    for match in SENTENCE_END.finditer(text):
        if match[1] != "." or not SENTENCE_ABBREVIATION.search(text, 0, match.start()):
            boundaries.append(match.end())
    sentences = [text[start:end] for start, end in pairwise(boundaries)]
    tail = text[boundaries[-1]:]
    # A citation in unfinished prose applies to its line. In a regular table
    # a cell fragment cannot cite names outside the link label.
    if not table_cell:
        sentences.extend(tail.splitlines(keepends=True))
        tail = ""
    for index, sentence in enumerate(sentences):
        if (CITATION_LINK in sentence or ARXIV_ID.search(sentence)
                or source_ids.intersection(SOURCE_ID.findall(sentence))):
            sentences[index] = re.sub(r"[^\n]", " ", sentence)
    return "".join(sentences) + tail


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


def bare_url_text(match):
    url = match[0]
    target = url.rstrip(".,!?;:\"'”’")
    return (web_link_text(target) or " ") + url[len(target):]


def inline_text(relative, tokens, tree_paths, *, schema_example=False, keep_link_labels=False):
    """Retain checkable inline text, including unresolved file names."""
    parts = []
    skip_label = False
    for index, token in enumerate(tokens):
        if token.type == "link_close" or (token.type == "html_inline" and HTML_LINK_CLOSE.fullmatch(token.content)):
            skip_label = False
            continue
        if skip_label:
            continue
        if token.type == "link_open":
            target = token.attrGet("href")
            if (citation := web_link_text(target)) is not None:
                parts.append(citation)
                skip_label = not keep_link_labels
            elif not urlsplit(target).netloc and tree_paths.isdisjoint(tree_candidates(relative, target, link=True)):
                parts.extend((" ", urlsplit(target).path, " "))
        elif token.type == "text":
            parts.append(WEB_URL.sub(bare_url_text, token.content))
        elif token.type == "code_inline":
            if not tree_paths.isdisjoint(tree_candidates(relative, token.content)):
                parts.append(" ")
            else:
                literal = token.content
                if literal in ("codex", "antigravity"):
                    literal = literal.capitalize()
                parts.append(fence_text(literal) if schema_example else literal)
        elif token.type == "html_inline" and (match := HTML_LINK.match(token.content)):
            target = unescape(next(value for value in match.groups() if value is not None))
            citation = web_link_text(target)
            parts.append(citation or " ")
            if citation is not None and not keep_link_labels:
                skip_label = any(later.type == "html_inline" and HTML_LINK_CLOSE.fullmatch(later.content)
                                 for later in tokens[index + 1:])
        elif token.type in ("image", "html_inline"):
            parts.append(token.content)
    return "".join(parts)


def page_violations(relative, source, match_paths=None):
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
    source_ids, source_rows, paragraphs, table_cells = citation_context(tokens)
    fences = {number for token in tokens if token.type == "fence" for number in range(*token.map)}
    schema_examples = set()
    specification = relative.startswith("docs/contracts/")
    if specification:
        headings = [token for token in tokens if token.type == "heading_open"]
        for index, heading in enumerate(headings):
            if SCHEMA_EXAMPLE.search(lines[heading.map[0]]):
                end = headings[index + 1].map[0] if index + 1 < len(headings) else len(lines)
                schema_examples.update(range(heading.map[1], end))

    inlines = [
        [] if index in fences else MARKDOWN.parseInline(line, env)[0].children
        for index, line in enumerate(lines)
    ]
    tree_paths = set()
    if match_paths:
        cells = (cell.children for row in table_cells.values() for cell in row)
        tree_paths = match_paths(set(inline_paths(relative, chain(inlines, cells))))
    # The player-host restriction also applies to source labels.
    visible = [
        line if index in fences else inline_text(relative, inlines[index], tree_paths, keep_link_labels=True)
        for index, line in enumerate(lines)
    ]
    checked = [
        line if index in fences else inline_text(relative, inlines[index], tree_paths,
                                                 schema_example=index in schema_examples)
        for index, line in enumerate(lines)
    ]
    if specification:
        for index in fences:
            checked[index] = fence_text(checked[index])
    for start, end in paragraphs:
        checked[start:end] = uncited_text("\n".join(checked[start:end]), source_ids).split("\n")
    for index, cells in table_cells.items():
        checked[index] = " ".join(
            uncited_text(inline_text(relative, cell.children, tree_paths), source_ids, table_cell=True)
            for cell in cells
        )

    found = []
    adapter = relative == PLAYER_ADAPTER
    for index, line in enumerate(lines):
        if line in reproduced:
            continue
        if not adapter and PLAYER_HOST.search(visible[index]):
            found.append(f"{relative}:{index + 1}: {line}")
            continue
        if index in source_rows:
            continue
        text = checked[index]
        if adapter:
            text = ADAPTER_ROUTE.sub(" ", text)
        if AGENT.search(text) or PROVIDER_OR_MODEL.search(text):
            found.append(f"{relative}:{index + 1}: {line}")
    return found


def violations():
    with git_tree_paths(ROOT) as match_paths:
        found = [hit for relative, source in page_scope() for hit in page_violations(relative, source, match_paths)]
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

    ordinary = "pi, a medieval codex, a literary opus, a haiku, a fable, carbon, neon and a flash."
    assert page_violations("docs/setup.md", current_page(ordinary)) == []


def test_lowercase_commands_and_joined_products_are_refused():
    relative = "docs/setup.md"
    commands = (
        "Run `codex login`.", "Run `codex --version`.", "Run `codex mcp add enactive`.",
        "Run codex mcp list.", "Use the codex CLI.", "Run `claude --version`.", "Run `agy --version`.",
        "Run claude mcp list.", "Run agy --version.", "Use the claude CLI.", "Use the agy CLI.",
        "ClaudeCode", "codex-cli", "agy-cli", "antigravity",
        "codex 0.171.0", "claude 2.1.329", "agy 1.0", "the codex command", "the claude command",
        "the agy command", "npx codex", "brew install codex", "npm install -g codex", "codex_home",
        "my_codex", "claude_code",
    )
    for command in commands:
        assert page_violations(relative, current_page(command)) == [f"{relative}:5: {command}"]
    for ordinary in ("A medieval codex contains a sonnet.", "a codex-like book"):
        assert page_violations(relative, current_page(ordinary)) == []


def test_model_tiers_match_in_context_in_any_case():
    relative = "docs/setup.md"
    for name in (
        "sonnet 5.5", "haiku 5.5", "fable 5.2", "opus-5-5", "sonnet-5-5", "haiku-5-5",
        "the sol arm", "the astra arm", "claude-opus-5-5", "gpt-6.2-sol", "gpt-6.2-astra", "gemini-4-neon",
    ):
        assert page_violations(relative, current_page(name)) == [f"{relative}:5: {name}"]
    for tier in ("opus", "terra", "sonnet", "haiku", "fable", "sol", "astra", "luna", "neon",
                 "carbon", "argon", "flash", "llama"):
        for name in (f"{tier} 5.2", f"routed-{tier}", f"{tier}-5-2", f"{tier} arm",
                     f"{tier.upper()} MODEL", f"{tier} tier"):
            assert page_violations(relative, current_page(name)) == [f"{relative}:5: {name}"]
        assert page_violations(relative, current_page(f"An ordinary {tier}.")) == []


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


def test_outside_citations_are_limited_to_their_sentence_or_keyed_source_row():
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
        "  The cited result also used Claude Code.",
        "  - A related project should use Anthropic.",
        "- Use Anthropic for new project work (S99).",
        "[Anthropic's paper](https://example.org/study) describes the result for Pi.",
        "Use Gemini locally ([project issue](https://github.com/CVX-Hull/enactive/issues/873)).",
        "Use Codex locally.",
    )
    assert page_violations(relative, body) == [
        f"{relative}:{body.splitlines().index(line) + 1}: {line}" for line in expected
    ]


def test_only_keyed_rows_of_source_tables_get_the_row_exemption():
    relative = "docs/research-example.md"
    body = current_page("""| Source | Note |
| --- | --- |
| S12 | Anthropic, study methods |
| Our pick: Opus for lead | x |

| Role | Model |
| --- | --- |
| Lead | Opus [card](https://x.org) |
| S99 | OpenAI |

The paper studied Opus (S12).
The paper studied Opus (S99).
""")
    assert page_violations(relative, body) == [
        f"{relative}:8: | Our pick: Opus for lead | x |",
        f"{relative}:12: | Lead | Opus [card](https://x.org) |",
        f"{relative}:13: | S99 | OpenAI |",
        f"{relative}:16: The paper studied Opus (S99).",
    ]


def test_an_arxiv_id_in_the_first_cell_exempts_a_source_row():
    relative = "docs/research-example.md"
    body = current_page("""| Source | Flags |
| --- | --- |
| TwinRouterBench 2605.18859 | V; router diagnostic = Opus 4.6, one prompt |
| TwinRouterBench | Opus 4.6 |
| TwinRouterBench | Opus 4.6 (2605.18859) |

| Role | Model |
| --- | --- |
| Lead 2605.18859 | Opus 4.6 |
""")
    assert page_violations(relative, body) == [
        f"{relative}:8: | TwinRouterBench | Opus 4.6 |",
        f"{relative}:9: | TwinRouterBench | Opus 4.6 (2605.18859) |",
        f"{relative}:13: | Lead 2605.18859 | Opus 4.6 |",
    ]


def test_a_bare_url_cites_its_own_sentence_only():
    relative = "docs/research-example.md"
    body = "The study used Opus (see https://example.org/x). Our lead uses Opus."
    assert page_violations(relative, current_page(body.split(" Our")[0])) == []
    assert page_violations(relative, current_page(body)) == [f"{relative}:5: {body}"]
    body = "The study used Opus (see https://docs.anthropic.com)."
    assert page_violations(relative, current_page(body)) == [f"{relative}:5: {body}"]
    body = "The study used Opus (see `https://example.org/x`)."
    assert page_violations(relative, current_page(body)) == [f"{relative}:5: {body}"]


def test_citations_allow_names_only_in_their_own_sentence():
    relative = "docs/research-example.md"
    for line in (
        "We use Opus 5.5 for the lead. See [a study](https://example.org/x).",
        "Our lead model is Opus ([docs](https://docs.anthropic.com)).",
        "Our lead model is Opus ([docs](https://github.com/openai/codex)).",
        'Our lead model is Opus (<a href="https://docs.anthropic.com">docs</a>).',
    ):
        assert page_violations(relative, current_page(line)) == [f"{relative}:5: {line}"]
    for line in (
        'Use Opus <a href="https://x.org">x</a>.',
        "The paper used Opus (2605.18859).",
        "We chose Opus; compare arXiv:2601.01234.",
    ):
        assert page_violations(relative, current_page(line)) == []

    body = current_page("""- We use Opus.
  See [a study](https://example.org/x).

| ID | Source |
| --- | --- |
| S1 | An outside study |

The project's curator runs on Opus (S1).
""")
    assert page_violations(relative, body) == [f"{relative}:5: - We use Opus."]


def test_external_link_labels_can_name_their_source():
    relative = "docs/research-example.md"
    for line in (
        "- Context as a budget: [Anthropic, effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).",
        "[Anthropic's paper](https://example.org/study)",
        '| Source | <a href="https://docs.anthropic.com">Anthropic</a> |\n| --- | --- |',
    ):
        assert page_violations(relative, current_page(line)) == []
    for line in (
        "Use Anthropic ([Anthropic's paper](https://www.anthropic.com/engineering)).",
        'Use Anthropic (<a href="https://docs.anthropic.com">Anthropic</a>).',
        "[OpenAI](https://github.com/CVX-Hull/enactive/issues/873) is the default.",
        "[Anthropic's paper](https://example.org/study) describes the result for Pi.",
    ):
        assert page_violations(relative, current_page(line)) == [f"{relative}:5: {line}"]


def test_abbreviations_do_not_end_cited_sentences():
    relative = "docs/research-example.md"
    for line in (
        "[Smith et al.](https://example.org/x) evaluated Opus.",
        "The paper ([x](https://example.org/x)) tested, e.g. Opus and Sonnet.",
        "Smith et al. ([paper](https://example.org/x)) evaluated Opus.",
    ):
        assert page_violations(relative, current_page(line)) == []
    for abbreviation in ("et al.", "e.g.", "i.e.", "cf.", "Fig.", "vs.", "A."):
        study = f"The study ([x](https://example.org/x)) includes {abbreviation}\nOpus."
        assert page_violations(relative, current_page(study)) == []
        project = f"{study} Our lead uses Opus."
        assert page_violations(relative, current_page(project)) == [
            f"{relative}:6: Opus. Our lead uses Opus."
        ]


def test_citations_in_unpunctuated_prose_apply_to_their_line():
    relative = "docs/research-example.md"
    body = current_page("Lead: Opus\nReviewer: Sonnet\nSee [benchmarks](https://example.org/x)")
    assert page_violations(relative, body) == [f"{relative}:5: Lead: Opus", f"{relative}:6: Reviewer: Sonnet"]
    body = current_page("1. Our lead uses Opus\n   [x](https://example.org/x)")
    assert page_violations(relative, body) == [f"{relative}:5: 1. Our lead uses Opus"]
    assert page_violations(relative, current_page("Lead: Opus ([benchmarks](https://example.org/x))")) == []


def test_provider_owned_sites_do_not_cite_names_outside_their_labels():
    relative = "docs/research-example.md"
    for line in (
        "Lead is GPT-5 ([x](https://openai.github.io/x)).",
        "Lead is GPT-5 ([x](https://github.com/google-gemini/gemini-cli)).",
        "Lead is GPT-5 ([x](https://github.com/meta-llama/llama)).",
        "Lead is Qwen ([card](https://huggingface.co/Qwen/Qwen3-32B)).",
        "Lead is Qwen ([card](https://huggingface.co/DeepSeek-AI/DeepSeek-V3)).",
    ):
        assert page_violations(relative, current_page(line)) == [f"{relative}:5: {line}"]
    for link in ("https://independent-lab.github.io/x", "https://github.com/independent-lab/x",
                 "https://huggingface.co/independent-lab/Qwen3-study"):
        assert page_violations(relative, current_page(f"The study used Qwen ([card]({link})).")) == []


def test_tree_paths_depend_on_the_index_and_ignore_rules(tmp_path, tmp_path_factory, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "OpenAI").mkdir()
    (tmp_path / "OpenAI" / "tracked.txt").touch()
    (tmp_path / "Codex.md").touch()
    (tmp_path / ".gitignore").write_text(".claude/settings.local.json\n.claude/worktrees/\n")
    subprocess.run(["git", "init", "-q", "--template="], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", ".gitignore", "Codex.md", "OpenAI/tracked.txt"], cwd=tmp_path, check=True)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.ignorecase")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    system_temp = tmp_path_factory.mktemp("name-check-system-temp")
    monkeypatch.setattr(tempfile, "tempdir", str(system_temp))
    (tmp_path / "Untracked-Codex.md").touch()
    relative = "docs/setup.md"
    body = current_page("""Use `Codex.md:2` and ``../OpenAI/``.
See [setup](../Codex.md#claude-code).
[OpenAI](../Codex.md) is the default.
Use `OpenAI/missing.json`.
See [setup](../missing/Codex.md).
Use `Untracked-Codex.md`.
Generated `.claude/settings.local.json` is ignored.
See [settings](../.claude/settings.local.json).
See `.claude/worktrees/`.
Use `:(glob)Codex.md`.
Use `.Claude/worktrees/`.
Use `.CLAUDE/settings.local.json`.
""")
    expected = [
        f"{relative}:7: [OpenAI](../Codex.md) is the default.",
        f"{relative}:8: Use `OpenAI/missing.json`.",
        f"{relative}:9: See [setup](../missing/Codex.md).",
        f"{relative}:10: Use `Untracked-Codex.md`.",
        f"{relative}:14: Use `:(glob)Codex.md`.",
        f"{relative}:15: Use `.Claude/worktrees/`.",
        f"{relative}:16: Use `.CLAUDE/settings.local.json`.",
    ]
    with git_tree_paths(tmp_path) as match_paths:
        scratch, = system_temp.iterdir()
        assert (scratch / ".git").is_dir()
        assert page_violations(relative, body, match_paths) == expected
    assert not list(system_temp.iterdir())
    (tmp_path / ".claude" / "worktrees").mkdir(parents=True)
    (tmp_path / ".claude" / "settings.local.json").touch()
    with git_tree_paths(tmp_path) as match_paths:
        assert page_violations(relative, body, match_paths) == expected


def test_page_scan_reads_only_tracked_markdown(tmp_path, monkeypatch):
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    (tmp_path / ".worktrees").mkdir()
    (tmp_path / ".gitignore").write_text(".worktrees/\n")
    tracked = current_page("Use Codex locally.")
    (tmp_path / "tracked.md").write_text(tracked)
    subprocess.run([*GIT, "init", "-q", "--template="], cwd=tmp_path, check=True)
    subprocess.run([*GIT, "add", ".gitignore", "tracked.md"], cwd=tmp_path, check=True)
    (tmp_path / ".worktrees" / "ignored.md").write_text(current_page("Use Anthropic locally."))
    (tmp_path / "untracked.md").write_text(current_page("Use OpenAI locally."))
    assert list(page_scope()) == [("tracked.md", tracked)]
    assert violations() == ["tracked.md:5: Use Codex locally."]


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
