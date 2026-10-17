#!/usr/bin/env python3
"""Validate Markdown stewardship metadata, without making content-truth claims."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

try:
    import frontmatter
    from yaml import YAMLError
except ImportError as error:
    raise SystemExit("Development dependencies are missing; use .venv/bin/python after installing requirements-dev.lock (see docs/setup.md).") from error

from tools.governance import local_reference, schema_errors

ROOT_DOCUMENTS = ("README.md", "AGENTS.md", "NOTICE.md")


def check_metadata(root: Path) -> list[str]:
    errors = []
    yaml_handler = frontmatter.YAMLHandler()
    paths = [*(root / name for name in ROOT_DOCUMENTS), *sorted((root / "docs").rglob("*.md"))]
    for path in paths:
        label = str(path.relative_to(root))
        try:
            if not path.resolve().is_relative_to(root.resolve()):
                errors.append(f"{label}: document escapes repository")
                continue
            text = path.read_text()
            if not yaml_handler.detect(text):
                errors.append(f"{label}: missing YAML front matter")
                continue
            metadata = frontmatter.loads(text, handler=yaml_handler).metadata
            # YAML's safe loader recognizes unquoted calendar dates. JSON Schema
            # expects ISO strings; preserve other types so it can reject them.
            if type(metadata.get("date")) is date:
                metadata["date"] = metadata["date"].isoformat()
            invalid = schema_errors(root, "document", metadata, label)
            errors.extend(invalid)
            if invalid:
                continue
            if metadata["status"] == "superseded":
                reference = metadata["replacement"]
                if (not local_reference(root, reference)
                        or (root / reference.split("#", 1)[0]).resolve() == path.resolve()):
                    errors.append(f"{label}: invalid or missing local replacement {reference!r}; cannot replace self")
        except (OSError, ValueError, TypeError, YAMLError) as error:
            errors.append(f"{label}: invalid document metadata: {error}")
    return errors


def main() -> int:
    errors = check_metadata(ROOT)
    if errors:
        print("Document metadata failed:\n" + "\n".join(errors), file=sys.stderr)
        return 1
    print("Document stewardship metadata: passed; content truth was not verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
