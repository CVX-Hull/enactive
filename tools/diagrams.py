#!/usr/bin/env python3
"""Render Mermaid locally; check input/output receipts, never claim semantic truth."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = Path("docs/diagrams")
RECEIPT = DIRECTORY / "rendered.json"
CONFIGURATION = ("package.json", "package-lock.json", ".puppeteerrc.cjs",
                 "docs/diagrams/config.json", "docs/diagrams/browser.json", "tools/diagrams.py")
CACHES = (".cache/diagrams", ".cache/puppeteer", ".cache/puppeteer-tmp")


def require_local(root: Path, paths: list[Path]) -> None:
    for path in paths:
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Diagram path escapes repository: {path}")


def renderer_environment(root: Path) -> dict[str, str]:
    # Puppeteer accepts version, download, executable and directory overrides.
    # Use the lock-selected browser and local configuration for installs and renders.
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("PUPPETEER_")}
    environment.update(PUPPETEER_CACHE_DIR=str(root / ".cache/puppeteer"),
                       PUPPETEER_TMP_DIR=str(root / ".cache/puppeteer-tmp"),
                       PUPPETEER_BROWSER="chrome")
    return environment


def preflight(root: Path) -> list[Path]:
    diagrams = sources(root)
    require_local(root, [root / name for name in (*CONFIGURATION, *CACHES)]
                  + diagrams + [path.with_suffix(".svg") for path in diagrams]
                  + [root / RECEIPT])
    return diagrams


def install_browser(root: Path) -> None:
    require_local(root, [root / name for name in (*CONFIGURATION, *CACHES)])
    executable = root / "node_modules/.bin/puppeteer"
    if not executable.is_file():
        raise ValueError("Local Puppeteer CLI missing; follow docs/setup.md")
    subprocess.run([str(executable), "browsers", "install", "chrome"], cwd=root,
                   env=renderer_environment(root), check=True)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(root: Path) -> list[Path]:
    found = sorted((root / DIRECTORY).glob("*.mmd"))
    if not found:
        raise ValueError("No Mermaid sources found")
    for path in found:
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Diagram source escapes repository: {path}")
    return found


def receipt(root: Path) -> dict:
    diagrams = preflight(root)
    inputs = [root / name for name in CONFIGURATION] + diagrams
    outputs = [path.with_suffix(".svg") for path in diagrams]
    return {"schema_version": 1,
            "inputs": {str(path.relative_to(root)): digest(path) for path in inputs},
            "outputs": {str(path.relative_to(root)): digest(path) for path in outputs}}


def check_receipt(root: Path) -> None:
    preflight(root)
    try:
        saved = json.loads((root / RECEIPT).read_text())
        if saved != receipt(root):
            raise ValueError("Diagram inputs or SVGs changed; render with tools/diagrams.py --write and inspect the result")
    except FileNotFoundError as error:
        raise ValueError("Missing diagram output/receipt; run tools/diagrams.py --write after installing local tools") from error


def check_accessibility(path: Path) -> None:
    element = ET.fromstring(path.read_bytes())
    for tag in ("title", "desc"):
        item = element.find(f"{{http://www.w3.org/2000/svg}}{tag}")
        if item is None or not (item.text or "").strip():
            raise ValueError(f"{path.name}: missing accessible {tag}; add accTitle/accDescr to source")
    if not element.get("id"):
        raise ValueError(f"{path.name}: missing SVG ID; scoped Mermaid styles would not apply")


def render(root: Path, source: Path, output: Path) -> None:
    require_local(root, [source, output] + [root / name for name in (*CONFIGURATION, *CACHES)])
    executable = root / "node_modules/.bin/mmdc"
    if not executable.is_file():
        raise ValueError("Local Mermaid CLI missing; follow docs/setup.md (checks never install tools)")
    environment = renderer_environment(root)
    (root / ".cache/puppeteer-tmp").mkdir(parents=True, exist_ok=True)
    command = [str(executable), "-i", str(source), "-o", str(output),
               "-c", str(root / DIRECTORY / "config.json"),
               "-p", str(root / DIRECTORY / "browser.json"),
               "--size", "1000", "--svgId", "cdda-" + source.stem, "--quiet"]
    subprocess.run(command, cwd=root, env=environment, check=True, timeout=60,
                   capture_output=True, text=True)
    check_accessibility(output)


def check_or_write(root: Path, *, write: bool = False) -> None:
    diagrams = preflight(root)
    if not write:
        check_receipt(root)
    cache = root / ".cache/diagrams"
    cache.mkdir(parents=True, exist_ok=True)
    # Render all before publishing any; a bad diagram must not produce a new receipt.
    with tempfile.TemporaryDirectory(prefix="render-", dir=cache) as temporary:
        pending = []
        for source in diagrams:
            output = Path(temporary) / source.with_suffix(".svg").name
            render(root, source, output)
            pending.append((output, source.with_suffix(".svg")))
        if write:
            for output, destination in pending:
                destination.write_bytes(output.read_bytes())
            (root / RECEIPT).write_text(json.dumps(receipt(root), indent=2) + "\n")
        else:
            for _, destination in pending:
                check_accessibility(destination)
    print("Diagram rendering and input/output receipts: passed; inspect meaning and readability separately.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--write", action="store_true", help="regenerate tracked SVGs and their receipt")
    operation.add_argument("--install-browser", action="store_true", help="explicitly download the pinned browser into the project cache")
    args = parser.parse_args()
    try:
        if args.install_browser:
            install_browser(ROOT)
        else:
            check_or_write(ROOT, write=args.write)
        return 0
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as error:
        print(f"Diagrams failed: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
