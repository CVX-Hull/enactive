#!/usr/bin/env python3
"""Bounded repository checks; no project imports, native execution or evidence claims."""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path, PurePosixPath
import re
import sys

try:
    from jsonschema import Draft202012Validator, FormatChecker
    from jsonschema.exceptions import SchemaError
except ImportError as error:
    raise SystemExit("Development dependencies are missing; use .venv/bin/python after installing requirements-dev.lock (see docs/setup.md).") from error

ROOT = Path(__file__).resolve().parents[1]
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


def document_mappings(text: str) -> dict[str, tuple[list[str], list[str]]]:
    result = {}
    for match in re.finditer(r"^## (S-[A-Z]+)\b(.*?)(?=^## |\Z)", text, re.M | re.S):
        body = match.group(2)
        principles = re.findall(r"^Principles: (.+)$", body, re.M)
        controls = re.findall(r"^Controls: (.+)$", body, re.M)
        result[match.group(1)] = (
            re.findall(r"P-[A-Z]+", principles[0]) if len(principles) == 1 else [],
            re.findall(r"C-[A-Z]+", controls[0]) if len(controls) == 1 else [])
    return result


def schema_errors(root: Path, name: str, data: object, label: str) -> list[str]:
    schema = json.loads((root / "schemas" / f"{name}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [f"{label}: schema violation at {error.json_path}: {error.message}"
            for error in sorted(validator.iter_errors(data), key=lambda e: str(e.json_path))]


def check_lifecycle(root: Path, controls: list[dict], as_of: date) -> list[str]:
    """Validate records. A passed next_review date is not an error: controls are reviewed when they
    fail, are bypassed or cost more than expected, not on a calendar (ADR 010)."""
    errors = []
    by_id = {control["id"]: control for control in controls}
    for control in controls:
        identifier = control["id"]
        status = control["status"]
        if status in ("deprecated", "retired") and not control["rationale"]:
            errors.append(f"{identifier}: {status} requires rationale")
        replacement = control["replacement"]
        if replacement == identifier:
            errors.append(f"{identifier}: replacement cannot reference self")
        elif replacement is not None and replacement not in by_id:
            errors.append(f"{identifier}: unknown replacement {replacement}")
        visited = {identifier}
        cursor = replacement
        while cursor in by_id:
            if cursor in visited:
                errors.append(f"{identifier}: replacement cycle")
                break
            visited.add(cursor)
            cursor = by_id[cursor]["replacement"]
        exercise = control["last_exercise"]
        review = control["maintenance_review"]
        due = date.fromisoformat(control["next_review"]) if control["next_review"] else None
        for field, record in (("last_exercise", exercise), ("maintenance_review", review)):
            if record is None:
                continue
            if date.fromisoformat(record["date"]) > as_of:
                errors.append(f"{identifier}: {field} date is in the future as of {as_of}")
            for reference in record["evidence"]:
                if not local_reference(root, reference):
                    errors.append(f"{identifier}: invalid or missing {field} evidence reference {reference!r}")
        if status in ("active", "deprecated"):
            if review is None:
                errors.append(f"{identifier}: {status} requires maintenance review")
            if due is None:
                errors.append(f"{identifier}: {status} requires next_review")
        if review is not None:
            reviewed = date.fromisoformat(review["date"])
            if due is not None:
                if due < reviewed:
                    errors.append(f"{identifier}: next_review is before maintenance review")
                if status in ("active", "deprecated") and (due - reviewed).days > 90:
                    errors.append(f"{identifier}: next_review exceeds 90 days after maintenance review")
        elif due is not None:
            errors.append(f"{identifier}: next_review requires a maintenance review")
    return errors


def check_registry(root: Path, registry: dict, *, as_of: date | None = None) -> list[str]:
    errors = schema_errors(root, "control-registry", registry, "registry")
    if errors:
        return errors
    errors += check_lifecycle(root, registry["controls"], as_of or date.today())
    principles = re.findall(r"^## (P-[A-Z]+)\b", (root / "docs/charter.md").read_text(), re.M)
    if len(principles) != len(set(principles)):
        errors.append("charter: duplicate principle ID")
    engineering = (root / "docs/engineering.md").read_text()
    standard_ids = re.findall(r"^## (S-[A-Z]+)\b", engineering, re.M)
    if len(standard_ids) != len(set(standard_ids)) or set(standard_ids) != STANDARDS:
        errors.append("engineering: duplicate or missing mandatory standard IDs")
    mappings = document_mappings(engineering)
    control_ids = [control["id"] for control in registry["controls"]]
    active_ids = {control["id"] for control in registry["controls"] if control["status"] == "active"}
    for control in registry["controls"]:
        for reference in control["evidence"]:
            if not local_reference(root, reference):
                errors.append(f"{control['id']}: invalid or missing local evidence reference {reference!r}")
    if len(control_ids) != len(set(control_ids)):
        errors.append("registry: duplicate control ID")
    seen = set()
    used_controls = set()
    used_principles = set()
    for standard in registry["standards"]:
        identifier = standard["id"]
        if identifier in seen:
            errors.append(f"registry: duplicate standard ID {identifier}")
        seen.add(identifier)
        for field, known, used in (("principles", set(principles), used_principles),
                                   ("controls", set(control_ids), used_controls)):
            for item in standard[field]:
                if item not in known:
                    errors.append(f"{identifier}: unknown {field} reference {item}")
                elif field == "controls" and item not in active_ids:
                    errors.append(f"{identifier}: non-active control reference {item}")
            used.update(standard[field])
        if (standard["principles"], standard["controls"]) != mappings.get(identifier):
            errors.append(f"{identifier}: registry mapping differs from engineering.md")
    if seen != STANDARDS:
        errors.append(f"registry: mandatory standard mapping mismatch; missing={sorted(STANDARDS - seen)}, unknown={sorted(seen - STANDARDS)}")
    for label, orphaned in (("control", active_ids - used_controls),
                            ("principle", set(principles) - used_principles)):
        if orphaned:
            errors.append(f"registry: orphan {label} IDs {sorted(orphaned)}")
    return errors


def evidence_line(references: list[str]) -> str:
    """Implementation and current references linked; dated records counted and routed to the indexes."""
    records = [r for r in references if re.fullmatch(r"docs/(acceptance|changes)/[^/#]+\.md(#.*)?", r)]
    parts = [f"[{ref}](../{ref})" for ref in references if ref not in records]
    if not parts:  # a control evidenced only by dated records keeps them readable here
        return ", ".join(f"[{ref}](../{ref})" for ref in references)
    if records:
        parts.append(f"{len(records)} dated record{'s' if len(records) != 1 else ''} named in the "
                     "[registry](control-registry.json) ([acceptance index](acceptance/index.md), "
                     "[change index](changes/index.md))")
    return ", ".join(parts)


def render_map(registry: dict) -> str:
    lines = ["---", "owner: maintainer", "status: active",
             "review_trigger: Changed standards, mechanisms, evidence or coverage", "---", "",
             "# Control map", "", "<!-- Generated by tools/governance.py --write; edit control-registry.json. -->", "",
             "This is an implemented control inventory, not a test-run report.",
             "Review on changed standards, mechanisms, evidence or coverage. The",
             "[registry](control-registry.json) owns these mappings; [engineering](engineering.md)",
             "owns mandatory wording and [charter](charter.md) owns principles.", "",
             "Automatic controls run in the common lane. Runtime controls act in the live system;",
             "their tests cover only the stated cases. Manual controls require the named review",
             "or probe. Implementation and evidence links do not assert a current execution or pass.", "",
             "## Standards and principles", "", "| Standard | Principles | Controls |", "| --- | --- | --- |"]
    for standard in registry["standards"]:
        identifier = standard["id"]
        lines.append(f"| {identifier} | {', '.join(standard['principles'])} | {', '.join(standard['controls'])} |")
    lines += ["", "## Maintenance", "",
              "Dates are recorded evidence dates. A passed next review is not a check failure: a",
              "control is reviewed when it fails, is bypassed or costs more than expected.", "",
              "| Control | Lifecycle | Last exercise | Maintenance review | Effectiveness | Next review |",
              "| --- | --- | --- | --- | --- | --- |"]
    for control in registry["controls"]:
        exercise, review = control["last_exercise"], control["maintenance_review"]
        lines.append(f"| {control['id']} | {control['status']} | "
                     f"{exercise['date'] if exercise else 'unrecorded'} | "
                     f"{review['date'] if review else 'unreviewed'} | "
                     f"{review['effectiveness'] if review else 'unassessed'} | {control['next_review'] or 'none'} |")
    lines += ["", "## Mechanisms and coverage", ""]
    for control in registry["controls"]:
        lines += [f"### {control['id']} — {control['name']} ({control['mode']})", "",
                  f"{control['scope']} {control['mechanism']}", "",
                  f"Owner: {control['owner']}. Trigger: {control['trigger']}.",
                  f"Enforcement: {control['enforcement']}",
                  f"Failure response: {control['failure_response']}", "",
                  "Evidence / implementation: " + evidence_line(control["evidence"]) + ".", "",
                  f"Coverage gap: {control['limitations']}", ""]
        lines += [f"Lifecycle: {control['status']}. Rationale: {control['rationale'] or 'none recorded'}. "
                  f"Replacement: {control['replacement'] or 'none'}.", ""]
        exercise = control["last_exercise"]
        if exercise is None:
            lines += ["Last exercise: unrecorded; no execution claim.", ""]
        else:
            lines += [f"Last exercise: {exercise['date']}. Outcome: {exercise['outcome']}",
                      f"Scope: {exercise['scope']}",
                      "Exercise evidence: " + ", ".join(f"[{ref}](../{ref})" for ref in exercise["evidence"]) + ".", ""]
        review = control["maintenance_review"]
        if review is None:
            lines += ["Maintenance review: unrecorded.", ""]
        else:
            lines += [f"Maintenance review: {review['date']}. Effectiveness: {review['effectiveness']}.",
                      f"Findings: {review['findings']}", f"Cost: {review['cost']}",
                      f"Follow-up: {review['follow_up']}",
                      "Review evidence: " + ", ".join(f"[{ref}](../{ref})" for ref in review["evidence"]) + ".", ""]
        lines += [f"Next review: {control['next_review'] or 'none'}.", ""]
    lines += ["## Interpreting results", "",
              "Run `.venv/bin/python tools/check.py` for the portable lane; update this map with",
              "`.venv/bin/python tools/governance.py --write`. The latter validates before writing and",
              "does not run gameplay. Dated executions belong in [acceptance](acceptance/2026-10-17-mvp.md)",
              "and [work](work.md), with exact candidate, failures and unexecuted lanes.", ""]
    return "\n".join(lines)


def check_generated(root: Path, registry: dict) -> list[str]:
    path = root / "docs/controls.md"
    if not path.is_file() or path.read_text() != render_map(registry):
        return ["docs/controls.md is stale; run python tools/governance.py --write"]
    return []






def check_manifests(root: Path) -> list[str]:
    """Validate curated metadata, not availability, hashes of local bytes or gameplay."""
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


EVIDENCE_IDS = "schemas/evidence-ids.json"
# Where a schema id counts as defined: a schema file, a contract, or code.
DEFINING = ("schemas/*.schema.json", "docs/contracts/*.md", "harness/**/*.py", "tools/**/*.py", "tools/**/*.mjs")


def check_evidence_ids(root: Path) -> list[str]:
    """Every versioned `schema` a tracked evidence JSON declares is defined: named as a whole token by a schema
    file, contract or code, or listed as a frozen one-off shape in schemas/evidence-ids.json, whose entries must
    be exact."""
    registry = json.loads((root / EVIDENCE_IDS).read_text())["ids"]
    defining = "\n".join(path.read_text(errors="ignore") for pattern in DEFINING for path in root.glob(pattern)
                         if "node_modules" not in path.parts)
    declared: dict[str, list[str]] = {}
    for base in ("docs", "data"):
        for path in sorted((root / base).rglob("*.json")):
            try:
                schema = json.loads(path.read_text()).get("schema")
            except (ValueError, AttributeError):
                continue
            if isinstance(schema, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*/[0-9]+", schema):
                declared.setdefault(schema, []).append(str(path.relative_to(root)))
    named = lambda schema: re.search(rf"(?<![A-Za-z0-9_/-]){re.escape(schema)}(?![0-9])", defining) is not None
    errors = [f"{files[0]}: schema {schema!r} is defined nowhere; define it or list it in {EVIDENCE_IDS}"
              for schema, files in sorted(declared.items()) if schema not in registry and not named(schema)]
    for schema, entry in sorted(registry.items()):
        if sorted(entry["files"]) != sorted(declared.get(schema, [])):
            errors.append(f"{EVIDENCE_IDS}: {schema} lists {entry['files']}, but {declared.get(schema, [])} declare it")
        errors.extend(f"{EVIDENCE_IDS}: {schema} names a missing record {record!r}"
                      for record in entry["records"] if not local_reference(root, record))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="regenerate docs/controls.md after validation")
    args = parser.parse_args(argv)
    try:
        registry = json.loads((ROOT / "docs/control-registry.json").read_text())
        errors = check_registry(ROOT, registry)
        errors += check_manifests(ROOT)
        if not args.write and not errors:
            errors += check_generated(ROOT, registry)
        if errors:
            raise ValueError("\n".join(errors))
        if args.write:
            (ROOT / "docs/controls.md").write_text(render_map(registry))
            print("Generated docs/controls.md; no gameplay or evidence-byte verification performed.")
        else:
            print("Governance schemas, mappings, local references, map freshness: passed.")
        return 0
    except (OSError, ValueError, SyntaxError, SchemaError) as error:
        print(f"Governance failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
