#!/usr/bin/env python3
"""Portable controller checks; native compilation/gameplay are separate acceptance."""
from __future__ import annotations

import re
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCS = ("README.md", "AGENTS.md", "docs/engineering.md", "docs/architecture.md",
                 "docs/work.md", "docs/environment.md", "docs/research.md", "docs/setup.md")


def check_documents(root: Path) -> list[str]:
    errors = [f"Missing required document: {name}" for name in REQUIRED_DOCS
              if not (root / name).is_file()]
    markdown = [root / "README.md", root / "AGENTS.md", *sorted((root / "docs").rglob("*.md"))]
    for document in markdown:
        if not document.is_file():
            continue
        text = re.sub(r"```.*?```", "", document.read_text(), flags=re.S)
        for match in re.finditer(r"\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)", text):
            link = match.group(1).strip("<>")
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
    for directory in ("harness", "tools", "tests"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            compile(path.read_bytes(), str(path), "exec")
    print("Python syntax: passed", flush=True)
    node = shutil.which("node")
    if node is None:
        raise ValueError("Node.js is required for JavaScript syntax checks; use an existing/local runtime")
    for path in sorted((ROOT / "web").rglob("*.js")):
        run([node, "--check", "--input-type=module"], input=path.read_bytes())
    errors = check_documents(ROOT)
    if errors:
        raise ValueError("\n".join(errors))
    print("Required documents and local Markdown file links: passed", flush=True)
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
