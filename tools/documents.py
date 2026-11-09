#!/usr/bin/env python3
"""Document and record checks (C-DOCUMENTS): stewardship metadata, acceptance manifests, evidence schema ids,
standard/principle/control identifiers and the dated-record indexes. Structure only, no content-truth claims."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

try:
    import frontmatter
    from jsonschema import Draft202012Validator, FormatChecker
    from yaml import YAMLError
except ImportError as error:
    raise SystemExit("Development dependencies are missing; use .venv/bin/python after installing requirements-dev.lock (see docs/setup.md).") from error

ROOT_DOCUMENTS = ("README.md", "AGENTS.md", "NOTICE.md", "CONTRIBUTING.md", "SECURITY.md")
STANDARDS = {"S-UX", "S-ARCH", "S-PROTOCOL", "S-CODE", "S-DELIVERY", "S-OPS",
             "S-AGENT", "S-DOCS", "S-WORK", "S-MIGRATION", "S-EVIDENCE"}


def local_reference(root: Path, reference: object, *, exists: bool = True) -> bool:
    """Repository-relative POSIX paths only; resolve symlinks before containment."""
    if not isinstance(reference, str) or not reference or "\\" in reference:
        return False
    path_text = reference.split("#", 1)[0]
    path = PurePosixPath(path_text)
    if not path_text or path.is_absolute() or any(p in (".", "..") for p in path_text.split("/")):
        return False
    if ":" in path_text or "?" in path_text:
        return False
    target = (root / path).resolve()
    return target.is_relative_to(root.resolve()) and (not exists or target.is_file())


def schema_errors(root: Path, name: str, data: object, label: str) -> list[str]:
    schema = json.loads((root / "schemas" / f"{name}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [f"{label}: schema violation at {error.json_path}: {error.message}"
            for error in sorted(validator.iter_errors(data), key=lambda e: str(e.json_path))]


def check_identifiers(root: Path) -> list[str]:
    """The charter's principles are unique; engineering.md has each mandatory standard once, each with one
    Principles and one Controls line naming known principles and controls; the controls page lists each
    control once, and every control serves some standard."""
    errors = []
    principles = re.findall(r"^## (P-[A-Z]+)\b", (root / "docs/charter.md").read_text(), re.M)
    if len(principles) != len(set(principles)):
        errors.append("charter: duplicate principle ID")
    controls = re.findall(r"^\| (C-[A-Z]+) \|", (root / "docs/controls.md").read_text(), re.M)
    if len(controls) != len(set(controls)):
        errors.append("controls: duplicate control ID")
    engineering = (root / "docs/engineering.md").read_text()
    sections = {match.group(1): match.group(2)
                for match in re.finditer(r"^## (S-[A-Z]+)\b(.*?)(?=^## |\Z)", engineering, re.M | re.S)}
    if len(re.findall(r"^## (S-[A-Z]+)\b", engineering, re.M)) != len(sections) or set(sections) != STANDARDS:
        errors.append(f"engineering: mandatory standards differ; missing={sorted(STANDARDS - set(sections))}, "
                      f"unknown={sorted(set(sections) - STANDARDS)}")
    used: dict[str, set[str]] = {"Principles": set(), "Controls": set()}
    for standard, body in sorted(sections.items()):
        for label, pattern, known in (("Principles", r"P-[A-Z]+", set(principles)), ("Controls", r"C-[A-Z]+", set(controls))):
            lines = re.findall(rf"^{label}: (.+)$", body, re.M)
            if len(lines) != 1:
                errors.append(f"{standard}: needs exactly one {label} line")
                continue
            named = re.findall(pattern, lines[0])
            if not named:
                errors.append(f"{standard}: its {label} line names none")
            if len(named) != len(set(named)):
                errors.append(f"{standard}: its {label} line repeats an ID")
            errors += [f"{standard}: unknown {label.lower()[:-1]} {name}" for name in named if name not in known]
            used[label].update(named)
    if unused := sorted(set(controls) - used["Controls"]):
        errors.append(f"controls: {unused} serve no standard")
    if unused := sorted(set(principles) - used["Principles"]):
        errors.append(f"charter: principles {unused} serve no standard")
    return errors


def check_manifests(root: Path) -> list[str]:
    """Validate curated acceptance-manifest metadata, not availability, local bytes or gameplay."""
    errors = []
    paths = sorted((root / "docs/acceptance").glob("*-manifest.json"))
    if not paths:
        return ["acceptance: missing curated manifest"]
    for path in paths:
        label = str(path.relative_to(root))
        try:
            data = json.loads(path.read_text())
            invalid = schema_errors(root, "acceptance-manifest", data, label)
            if invalid:
                errors.extend(invalid)
                continue
            for field in ("report", "upstream_pin"):
                if not local_reference(root, data[field]):
                    errors.append(f"{label}: invalid or missing {field} reference")
            for reference in data["artifacts"]:
                if "#" in reference or not local_reference(root, reference, exists=False):
                    errors.append(f"{label}: invalid artifact reference {reference!r}")
            if data["video"] is not None:
                interval = data["video"]["capture_interval_ms"]
                if interval[1] <= interval[0]:
                    errors.append(f"{label}: video capture interval must end after it starts")
        except (OSError, ValueError) as error:
            errors.append(f"{label}: {error}")
    return errors


# Where a schema id counts as defined: a schema file, a contract, or code. Where a data file counts as read: code
# or a test. Dated record assets (docs/acceptance/assets, docs/assets) are defined by their record and not checked.
DEFINING = ("schemas/*.schema.json", "docs/contracts/*.md", "harness/**/*.py", "tools/**/*.py", "tools/**/*.mjs")
READERS = ("harness/**/*.py", "tools/**/*.py", "tools/**/*.mjs", "tests/**/*.py", "tests/**/*.mjs", "tests/**/*.cjs",
           "web/**/*.js")


def _text(root: Path, patterns: tuple[str, ...]) -> str:
    return "\n".join(path.read_text(errors="ignore") for pattern in patterns for path in root.glob(pattern)
                     if "node_modules" not in path.parts)


def check_data(root: Path) -> list[str]:
    """S-EVIDENCE's data rule. Every file under data/ is read by code or a test: its name appears in a reader, or
    the whole path of a directory holding it below data/ is a string literal there (`'data/x'`, or the joined
    segments `'data' / 'x'`), as when code lists that directory. Every
    versioned `schema` a data/ JSON declares is named as a whole token by a schema file, a contract or code."""
    data = root / "data"
    if not data.is_dir():
        return []
    readers = joined = _text(root, READERS)
    segment = re.compile(r"""(['"])([^'"\n]*)\1\s*/\s*(['"])([^'"\n]*)\3""")
    while (step := segment.sub(r"'\2/\4'", joined)) != joined:  # 'data' / 'x' -> 'data/x'
        joined = step
    literals = {a or b for a, b in re.findall(r"""'([^'\n]*)'|"([^"\n]*)\"""", joined)}
    literals |= {value.rstrip("/") for value in literals}
    defining = _text(root, DEFINING)
    errors = []
    for path in sorted(p for p in data.rglob("*") if p.is_file() and p.name != ".DS_Store"):
        parts = path.relative_to(root).parts
        if not (parts[-1] in readers or any("/".join(parts[:i]) in literals for i in range(len(parts) - 1, 1, -1))):
            errors.append(f"{'/'.join(parts)}: no code or test reads it or its directory; a file only a record "
                          "uses is that record's asset under docs/acceptance/assets/")
        if path.suffix != ".json":
            continue
        try:
            schema = json.loads(path.read_text()).get("schema")
        except (ValueError, AttributeError):
            continue
        if (isinstance(schema, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*/[0-9]+", schema)
                and not re.search(rf"(?<![A-Za-z0-9_/-]){re.escape(schema)}(?![0-9])", defining)):
            errors.append(f"{'/'.join(parts)}: schema {schema!r} is defined by no schema file, contract or code")
    return errors
# Current documents outside the root and docs/ trees; checked wherever they exist.
COMPONENT_DOCUMENTS = ("tools/player_host/README.md",)


def check_metadata(root: Path) -> list[str]:
    errors = []
    yaml_handler = frontmatter.YAMLHandler()
    paths = [*(root / name for name in ROOT_DOCUMENTS),
             *(root / name for name in COMPONENT_DOCUMENTS if (root / name).exists()),
             *sorted((root / "docs").rglob("*.md"))]
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
            # An unquoted " #" starts a YAML comment and silently truncates the value.
            if any(re.match(r"^[a-z_]+: [^'\"].* #", line) for line in text.split("\n---", 1)[0].splitlines()):
                errors.append(f"{label}: quote a front-matter value containing ' #'; YAML reads the rest as a comment")
            metadata = frontmatter.loads(text, handler=yaml_handler).metadata
            # YAML's safe loader recognizes unquoted calendar dates. JSON Schema
            # expects ISO strings; preserve other types so it can reject them.
            if type(metadata.get("date")) is date:
                metadata["date"] = metadata["date"].isoformat()
            invalid = schema_errors(root, "document", metadata, label)
            errors.extend(invalid)
            if invalid:
                continue
            if (path.is_relative_to(root / "docs/acceptance") and metadata["status"] != "historical"
                    and label not in INDEXES):
                errors.append(f"{label}: acceptance records must be historical evidence")
            if metadata["status"] == "superseded":
                reference = metadata["replacement"]
                if (not local_reference(root, reference)
                        or (root / reference.split("#", 1)[0]).resolve() == path.resolve()):
                    errors.append(f"{label}: invalid or missing local replacement {reference!r}; cannot replace self")
        except (OSError, ValueError, TypeError, YAMLError) as error:
            errors.append(f"{label}: invalid document metadata: {error}")
    return errors


#: Generated indexes of dated records: path -> (title, directory, what the directory holds).
INDEXES = {
    "docs/acceptance/index.md": ("Acceptance and audit records", "docs/acceptance",
                                 "dated acceptance, audit and run records"),
    "docs/changes/index.md": ("Change briefs", "docs/changes", "dated change briefs"),
}


def _cell(text: object) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def render_index(root: Path, index: str) -> str:
    """One row per dated record in the directory, newest first, from its front matter and title."""
    title, directory, holds = INDEXES[index]
    rows = []
    for path in sorted((root / directory).glob("*.md")):
        if path.name == "index.md":
            continue
        post = frontmatter.load(path)
        stamp = post.metadata.get("date")
        stamp = stamp.isoformat() if type(stamp) is date else str(stamp or "undated")
        heading = next((line[2:] for line in post.content.splitlines() if line.startswith("# ")), path.stem)
        rows.append((stamp, path.name, heading, post.metadata.get("scope", ""), post.metadata.get("status", "")))
    rows.sort(key=lambda row: (row[0] != "undated", row[0], row[1]), reverse=True)  # undated records last
    lines = ["---", "owner: lead", "status: active",
             "review_trigger: Generated; a record is added or its front matter changes", "---", "",
             f"# {title}", "", "<!-- Generated by python -m tools.documents --write; edit the records' front matter. -->", "",
             f"All {holds} in this directory, newest first, with the scope their front matter",
             "states. Records are dated evidence, not current instructions; the",
             "[documentation map](../documentation.md) routes to current owners.", "",
             "| Date | Record | Scope | Status |", "| --- | --- | --- | --- |"]
    lines += [f"| {stamp} | [{_cell(heading)}]({name}) | {_cell(scope)} | {status} |"
              for stamp, name, heading, scope, status in rows]
    return "\n".join(lines) + "\n"


def check_indexes(root: Path) -> list[str]:
    return [f"{index}: stale; run python -m tools.documents --write"
            for index in INDEXES if not (root / index).is_file() or (root / index).read_text() != render_index(root, index)]


def main(argv: list[str] | None = None) -> int:
    write = (argv if argv is not None else sys.argv[1:]) == ["--write"]
    if write:
        for index in INDEXES:
            (ROOT / index).write_text(render_index(ROOT, index))
        print("Generated the dated-record indexes.")
    errors = (check_metadata(ROOT) + check_manifests(ROOT) + check_data(ROOT) + check_identifiers(ROOT)
              + check_indexes(ROOT))
    if errors:
        print("Document checks failed:\n" + "\n".join(errors), file=sys.stderr)
        return 1
    print("Document metadata, acceptance manifests, the data rule, standard and control identifiers and "
          "record indexes: passed; content truth was not verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
