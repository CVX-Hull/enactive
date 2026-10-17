#!/usr/bin/env python3
"""Portable controller checks; native compilation/gameplay are separate acceptance."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
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


def check_documents(root: Path) -> list[str]:
    errors = [f"Missing required document: {name}" for name in REQUIRED_DOCS
              if not (root / name).is_file()]
    markdown = [*(root / name for name in ("README.md", "AGENTS.md", "NOTICE.md", "CONTRIBUTING.md", "SECURITY.md")), *sorted((root / "docs").rglob("*.md"))]
    parser = MarkdownIt("commonmark").enable("table")
    for document in markdown:
        if not document.is_file():
            continue
        for token in (child for block in parser.parse(document.read_text())
                      for child in (block.children or [])):
            link = token.attrGet("href") if token.type == "link_open" else (
                token.attrGet("src") if token.type == "image" else None)
            if link is None:
                continue
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (document.parent / unquote(parsed.path)).resolve()
            if not target.is_relative_to(root.resolve()) or not target.exists():
                errors.append(f"Broken local link in {document.relative_to(root)}: {link}")
    return errors


def run(command: list[str], **kwargs) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def main() -> int:
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
    errors = check_documents(ROOT)
    if errors:
        raise ValueError("\n".join(errors))
    print("Required documents and local Markdown file links: passed", flush=True)
    run([sys.executable, "-m", "tools.documents"])
    run([sys.executable, "tools/diagrams.py"])
    run([sys.executable, "tools/governance.py"])
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run([node, "tests/test_viewer.cjs"])
    run(["git", "diff", "--check"])
    run(["git", "diff", "--cached", "--check"])
    print("Portable checks passed. Native build and real gameplay were not tested.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, SyntaxError, subprocess.CalledProcessError) as error:
        print(f"Check failed: {error}", file=sys.stderr)
        raise SystemExit(1)
