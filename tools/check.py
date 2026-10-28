#!/usr/bin/env python3
"""Portable controller checks; native compilation/gameplay are separate acceptance."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import frontmatter
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import unquote, urlsplit

try:
    from markdown_it import MarkdownIt
except ImportError as error:
    raise SystemExit("Development dependencies are missing; use .venv/bin/python after installing requirements-dev.lock (see docs/setup.md).") from error

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCS = ("README.md", "AGENTS.md", "NOTICE.md", "CONTRIBUTING.md", "SECURITY.md", "docs/project-management.md", "docs/overview.md", "docs/charter.md",
                 "docs/engineering.md", "docs/architecture.md", "docs/protocol.md",
                 "docs/controls.md", "docs/runbook.md", "docs/work.md",
                 "docs/environment.md", "docs/research.md", "docs/setup.md")
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))
from tools.ci import COMPONENT_TESTS, SMOKE_TESTS


class _HTMLAnchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = set()
        self.text = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if value and (key == "id" or tag == "a" and key == "name"):
                self.anchors.add(value)

    def handle_data(self, data):
        self.text.append(data)


def _heading_text(children) -> str:
    parts = []
    for token in children or ():
        if token.type in ("text", "code_inline"):
            parts.append(token.content)
        elif token.type in ("softbreak", "hardbreak"):
            parts.append(" ")
        elif token.type == "image":
            parts.append(_heading_text(token.children))
        elif token.type == "html_inline":
            html = _HTMLAnchors()
            html.feed(token.content)
            parts.extend(html.text)
    return "".join(parts)


def check_documents(root: Path) -> list[str]:
    root = root.resolve()
    errors = [f"Missing required document: {name}" for name in REQUIRED_DOCS
              if not (root / name).is_file()]
    markdown = [*(root / name for name in ("README.md", "AGENTS.md", "NOTICE.md", "CONTRIBUTING.md", "SECURITY.md")), *sorted((root / "docs").rglob("*.md"))]
    parser = MarkdownIt("commonmark").enable("table")
    documents = {}
    for document in markdown:
        if not document.is_file():
            continue
        parsed = frontmatter.loads(document.read_text())
        tokens = parser.parse(parsed.content)
        headings, explicit, links = [], set(), []
        for index, block in enumerate(tokens):
            if block.type == "heading_open":
                headings.append(_heading_text(tokens[index + 1].children))
            if block.type in ("html_block", "html_inline"):
                html = _HTMLAnchors()
                html.feed(block.content)
                explicit.update(html.anchors)
            for child in block.children or ():
                if child.type == "html_inline":
                    html = _HTMLAnchors()
                    html.feed(child.content)
                    explicit.update(html.anchors)
                link = child.attrGet("href") if child.type == "link_open" else (
                    child.attrGet("src") if child.type == "image" else None)
                if link is not None:
                    links.append(link)
        documents[document.resolve()] = dict(headings=headings, anchors=explicit,
            links=links, current=parsed.metadata.get("status") in ("active", "proposed"))
    node = shutil.which("node")
    if node is None:
        errors.append("Node.js is required to validate GitHub Markdown fragments")
        return errors
    try:
        result = subprocess.run([node, str(ROOT / "tools/document_anchors.mjs")],
            input=json.dumps([doc["headings"] for doc in documents.values()]),
            text=True, capture_output=True, timeout=30, check=True, cwd=ROOT)
        for doc, anchors in zip(documents.values(), json.loads(result.stdout), strict=True):
            doc["anchors"].update(anchors)
    except (OSError, ValueError, subprocess.SubprocessError):
        errors.append("GitHub heading validator unavailable; install project-local package-lock.json dependencies")
        return errors
    graph = {}
    for document, doc in documents.items():
        graph[document] = set()
        for link in doc["links"]:
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc:
                continue
            target = (document.parent / unquote(parsed.path)).resolve() if parsed.path else document
            if not target.is_relative_to(root.resolve()) or not target.exists():
                errors.append(f"Broken local link in {document.relative_to(root)}: {link}")
                continue
            if target in documents:
                graph[document].add(target)
                # Frozen historical prose retains its original links. Current
                # guidance must point to an actual current or historical anchor.
                if doc["current"] and parsed.fragment and unquote(parsed.fragment) not in documents[target]["anchors"]:
                    errors.append(f"Broken local fragment in {document.relative_to(root)}: {link}")
    # Each responsibility index must actually lead to its canonical content.
    # This checks reachability, not task comprehension or arbitrary file sizes.
    for index, directory in (("protocol.md", "contracts"), ("engineering.md", "standards"),
                             ("project-management.md", "workflows"), ("runbook.md", "operations")):
        reachable, pending = set(), [(root / "docs" / index).resolve()]
        while pending:
            path = pending.pop()
            if path in reachable:
                continue
            reachable.add(path)
            pending.extend(graph.get(path, ()))
        for path in (root / "docs" / directory).rglob("*.md"):
            if documents.get(path.resolve(), {}).get("current") and path.resolve() not in reachable:
                errors.append(f"Current content is unreachable from docs/{index}: {path.relative_to(root)}")
    return errors


def run(command: list[str], **kwargs) -> None:
    print("+ " + " ".join(command), flush=True)
    started = time.perf_counter()
    try:
        subprocess.run(command, cwd=ROOT, check=True, **kwargs)
    finally:
        print(f"Command elapsed: {time.perf_counter() - started:.2f}s", flush=True)


def main(argv: list[str] | None = None) -> int:
    started = time.perf_counter()
    try:
        return _check(argv)
    finally:
        print(f"Checker elapsed: {time.perf_counter() - started:.2f}s", flush=True)


def _check(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--fast", action="store_true",
                       help="Checkpoint structure/lint checks only; no behavioral tests or diagram rendering")
    scope.add_argument("--profile", choices=("full", "editorial", "main-smoke", *COMPONENT_TESTS), default="full",
                       help="Strict validation profile (default: full)")
    args = parser.parse_args(argv)
    import_linter = Path(sys.executable).parent / "lint-imports"
    if not import_linter.is_file():
        raise ValueError(f"Import Linter is missing beside {sys.executable}; use the project .venv with requirements-dev.lock installed (see docs/setup.md)")
    for directory in ("harness", "tools", "tests"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            compile(path.read_bytes(), str(path), "exec")
    print("Python syntax: passed", flush=True)
    run([sys.executable, "-m", "ruff", "check", "--config", "pyproject.toml",
         "harness", "tools", "tests"])
    run([str(import_linter), "--config", "pyproject.toml", "--no-cache", "--no-logo"])
    node = shutil.which("node")
    if node is None:
        raise ValueError("Node.js is required for JavaScript syntax checks; use an existing/local runtime")
    for path in sorted((ROOT / "web").rglob("*.js")):
        run([node, "--check", "--input-type=module"], input=path.read_bytes())
    host = ROOT / "tools" / "player_host"
    for path in sorted((*host.glob("*.mjs"), *host.glob("test/*.mjs"))):
        run([node, "--check", str(path)])
    errors = check_documents(ROOT)
    if errors:
        raise ValueError("\n".join(errors))
    print("Required documents, current Markdown fragments and responsibility navigation: passed", flush=True)
    run([sys.executable, "-m", "tools.documents"])
    run([sys.executable, "tools/governance.py"] + (["--development"] if args.fast else []))
    if not args.fast:
        run([sys.executable, "tools/diagrams.py"])
    if not args.fast and args.profile != "editorial":
        targets = ("tests",) if args.profile == "full" else (
            SMOKE_TESTS if args.profile == "main-smoke" else COMPONENT_TESTS[args.profile])
        workers = "0" if args.profile == "main-smoke" else "4"
        run([sys.executable, "-m", "pytest", "-q", "-n", workers, "--dist", "worksteal" if args.profile == "full" else "loadfile",
             "--max-worker-restart=0", "--durations=20", *targets])
        run([node, "tests/test_viewer.cjs"])
    run(["git", "diff", "--check"])
    run(["git", "diff", "--cached", "--check"])
    if args.fast:
        print("Fast checkpoint checks passed. Behavioral tests, rendered diagrams, native build and real gameplay were not run.")
    elif args.profile == "editorial":
        print("Editorial checks passed. Runtime tests, viewer tests, full regression, native build and real gameplay were not run.")
    elif args.profile == "main-smoke":
        print("Selected smoke and viewer tests passed. Full regression, native build and real gameplay were not run.")
    elif args.profile in COMPONENT_TESTS:
        print(f"{args.profile.capitalize()} component and boundary smoke tests passed. Full regression, native build and real gameplay were not run.")
    else:
        print("Portable checks passed. Native build and real gameplay were not tested.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, SyntaxError, subprocess.CalledProcessError) as error:
        print(f"Check failed: {error}", file=sys.stderr)
        raise SystemExit(1)
