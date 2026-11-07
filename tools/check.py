#!/usr/bin/env python3
"""Portable computer/player checks; native compilation/gameplay are separate acceptance."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import os
import frontmatter
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
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
            pending.extend(target for target in graph.get(path, ())
                           if documents.get(target, {}).get("current"))
        for path in (root / "docs" / directory).rglob("*.md"):
            if documents.get(path.resolve(), {}).get("current") and path.resolve() not in reachable:
                errors.append(f"Current content is unreachable from docs/{index}: {path.relative_to(root)}")
    return errors


#: Each checker invocation keeps the full output of every subprocess command (except the short stdin-fed syntax
#: checks) in its own directory here, so a failure stays diagnosable even when terminal output was truncated (#421).
CHECK_LOGS = Path(".runtime") / "check-logs"
#: How long output may keep arriving after the command exits, from descendants that inherited the pipe.
DRAIN_SECONDS = 10
_log_directory: Path | None = None
_log_count = 0


def _log_path(command: list[str]) -> Path:
    global _log_directory, _log_count
    if _log_directory is None or not _log_directory.is_dir() or not _log_directory.is_relative_to(ROOT):
        (ROOT / CHECK_LOGS).mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        _log_directory, _log_count = Path(tempfile.mkdtemp(prefix=f"{stamp}-", dir=ROOT / CHECK_LOGS)), 0
    _log_count += 1
    name = "-".join(Path(part).name for part in command[:4])
    name = "".join(c if c.isalnum() or c in "._-" else "-" for c in name)[:60]
    return _log_directory / f"{_log_count:02d}-{name}.log"


class _Output:
    """Copies a command's merged output to its log and the terminal until stopped."""

    def __init__(self, stream, log):
        self.stream, self.log, self.lock, self.stopped = stream, log, threading.Lock(), False
        self.thread = threading.Thread(target=self._copy, daemon=True)
        self.thread.start()

    def _copy(self) -> None:
        for line in self.stream:
            with self.lock:
                if self.stopped:
                    return
                self.log.write(line)
                sys.stdout.write(line.decode(errors="replace"))
                sys.stdout.flush()

    def finish(self, timeout: float) -> bool:
        """Wait for the end of output; True when it ended, False when it was cut off after `timeout` seconds."""
        self.thread.join(timeout)
        with self.lock:
            self.stopped = True
        return not self.thread.is_alive()


def run(command: list[str], **kwargs) -> None:
    print("+ " + " ".join(command), flush=True)
    started = time.perf_counter()
    try:
        if "input" in kwargs:  # stdin-fed syntax checks: short, silent on success
            subprocess.run(command, cwd=ROOT, check=True, **kwargs)
            return
        path = _log_path(command)
        environment = {**os.environ, "PYTHONUNBUFFERED": "1"}  # keep stdout/stderr order as on a terminal
        with path.open("xb") as log:
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       env=environment, **kwargs)
            output = _Output(process.stdout, log)
            try:
                returncode = process.wait()
            except BaseException:  # as subprocess.run does: an interrupted check leaves no child running
                process.kill()
                process.wait()
                raise
            # A descendant that outlived the command (an orphaned fixture server, say) can hold the pipe open;
            # read what it still sends for a bounded time instead of waiting for it to exit.
            if output.finish(DRAIN_SECONDS):
                process.stdout.close()
            else:
                note = (f"Output pipe still held by a descendant {DRAIN_SECONDS}s after the command exited "
                        f"(status {returncode}); stopped reading.\n")
                log.write(note.encode())
                print(note, end="", flush=True)
        if returncode:
            print(f"Full output of the failed command: {path.relative_to(ROOT)}", flush=True)
            raise subprocess.CalledProcessError(returncode, command)
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
    run([sys.executable, "-m", "tools.run_ledger", "check"])
    run([sys.executable, "-m", "tools.evidence", "verify"] + ([] if args.fast else ["--full"]))
    from tools.evaluate import has_blocks
    generated = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "docs").rglob("*.md")
                       if has_blocks(path.read_text()))
    run([sys.executable, "-m", "tools.evaluate", "evaluate-table", "data/evaluation/run-metrics.jsonl",
         "--check", *generated])
    if not args.fast:
        run([sys.executable, "tools/diagrams.py"])
    if not args.fast and args.profile != "editorial":
        targets = ("tests",) if args.profile == "full" else (
            SMOKE_TESTS if args.profile == "main-smoke" else COMPONENT_TESTS[args.profile])
        workers = "0" if args.profile == "main-smoke" else "4"
        run([sys.executable, "-m", "pytest", "-q", "-n", workers, "--dist", "worksteal" if args.profile == "full" else "loadfile",
             "--max-worker-restart=0", "--durations=20", *targets])
        run([node, "tests/test_viewer.cjs"])
        run([node, "tests/test_investigation.cjs"])
        run([node, "tests/test_investigation_session.cjs"])
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
