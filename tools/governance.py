#!/usr/bin/env python3
"""Bounded repository checks; no project imports, native execution or evidence claims."""
from __future__ import annotations

import argparse
import ast
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


def check_lifecycle(root: Path, controls: list[dict], as_of: date, *,
                    warnings: list[str] | None = None) -> list[str]:
    """Validate records; an explicit warning sink relaxes only calendar expiry."""
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
            elif as_of > due:
                overdue = f"{identifier}: maintenance overdue since {due} (as of {as_of})"
                (errors if warnings is None else warnings).append(overdue)
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


def check_registry(root: Path, registry: dict, *, as_of: date | None = None,
                   warnings: list[str] | None = None) -> list[str]:
    errors = schema_errors(root, "control-registry", registry, "registry")
    if errors:
        return errors
    errors += check_lifecycle(root, registry["controls"], as_of or date.today(), warnings=warnings)
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
              "Dates are recorded evidence dates. Normal checks evaluate due dates as of the printed",
              "evaluation date; they do not renew records. Use `--as-of YYYY-MM-DD` to forecast.",
              "Active and deprecated controls warn after their due date in `tools/check.py --fast`;",
              "full checks remain strict. Event triggers can require earlier review.", "",
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
                  "Evidence / implementation: " + ", ".join(
                      f"[{ref}](../{ref})" for ref in control["evidence"]) + ".", "",
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


def dict_protocols(tree: ast.AST) -> list[object]:
    return [value.value if isinstance(value, ast.Constant) else None
            for node in ast.walk(tree) if isinstance(node, ast.Dict)
            for key, value in zip(node.keys, node.values)
            if isinstance(key, ast.Constant) and key.value == "protocol"]


def check_protocol(root: Path) -> list[str]:
    """Check bounded current wire forms across both channels; not a C++ parser."""
    native = (root / "native/cdda_harness.cpp").read_text()
    native = re.sub(r"//[^\n]*|/\*.*?\*/", "", native, flags=re.S)
    emitter = [int(v) for v in re.findall(r'out\.member\(\s*"protocol"\s*,\s*(\d+)\s*\)', native)]
    validator = [int(v) for v in re.findall(r'request\.get_int\(\s*"protocol"\s*\)\s*!=\s*(\d+)\s*\)', native)]
    control_emitter = [int(v) for v in re.findall(r'\\"protocol\\":(\d+)', native)]
    control_validator = [int(v) for v in re.findall(
        r'integer_member\(\s*request\s*,\s*"protocol"\s*\)\s*!=\s*(\d+)\s*', native)]
    controller = ast.parse((root / "harness/controller.py").read_text())
    server = ast.parse((root / "harness/server.py").read_text())
    cli = ast.parse((root / "harness/__main__.py").read_text())
    discovery_versions = [
        node.comparators[0].value if isinstance(node.comparators[0], ast.Constant) else None
        for node in ast.walk(cli)
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Subscript)
        and isinstance(node.left.value, ast.Name) and node.left.value.id == "config"
        and isinstance(node.left.slice, ast.Constant) and node.left.slice.value == "protocol"
        and len(node.ops) == 1 and isinstance(node.ops[0], ast.NotEq)]
    response_versions = []
    for function in controller.body:
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) and function.name in {"validate_state", "validate_control_response"}:
            for node in ast.walk(function):
                if (isinstance(node, ast.Compare) and isinstance(node.left, ast.Subscript)
                        and isinstance(node.left.value, ast.Name) and node.left.value.id == "value"
                        and isinstance(node.left.slice, ast.Constant) and node.left.slice.value == "protocol"
                        and len(node.ops) == 1 and isinstance(node.ops[0], ast.NotEq)):
                    value = node.comparators[0]
                    response_versions.append(value.value if isinstance(value, ast.Constant) else None)
    stored_versions = [
        node.comparators[0].value if isinstance(node.comparators[0], ast.Constant) else None
        for node in ast.walk(controller)
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Subscript)
        and isinstance(node.left.value, ast.Name) and node.left.value.id == "request"
        and isinstance(node.left.slice, ast.Constant) and node.left.slice.value == "protocol"
        and len(node.ops) == 1 and isinstance(node.ops[0], ast.NotEq)]
    viewer = (root / "web/app.js").read_text()
    viewer_versions = [int(v) for v in re.findall(r"displayed\.protocol\s*!==\s*(\d+)\b", viewer)]
    docs = [int(v) for v in re.findall(r"\bProtocol version: (\d+)\.", (root / "docs/protocol.md").read_text())]
    evidence = ast.parse((root / "harness/gameplay/evidence.py").read_text())
    evidence_versions = []
    for node in ast.walk(evidence):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "protocol" and isinstance(value, ast.Dict):
                    evidence_versions.extend(v.value if isinstance(v, ast.Constant) else None
                                             for k, v in zip(value.keys, value.values)
                                             if isinstance(k, ast.Constant) and k.value == "const")
    forms = {"native emitter": emitter, "native integer validators": control_validator,
             "native control emitter": control_emitter,
             "controller send": dict_protocols(controller), "controller validator": response_versions,
             "server advertisement": dict_protocols(server), "CLI discovery validator": discovery_versions,
             "stored request validator": stored_versions, "viewer validator": viewer_versions,
             "evidence validator": evidence_versions, "docs/protocol.md": docs}
    # Ordinary exchange, operator recovery and trusted mission recovery each
    # construct the same current native envelope; none is a fallback transport.
    expected_counts = {"native integer validators": 2, "controller send": 3, "controller validator": 2, "stored request validator": 2, "viewer validator": 2}
    errors = []
    if validator:
        errors.append("native protocol uses the removed coercive get_int form; review integer validator")
    if native.count('"protocol"') != 3 or native.count(r'\"protocol\"') != 1:
        errors.append("native protocol representation changed; review and update the bounded checker")
    for label, versions in forms.items():
        expected = expected_counts.get(label, 1)
        if len(versions) != expected:
            errors.append(f"{label}: protocol representation changed; expected {expected} recognized literals, found {versions!r}; review checker")
        elif any(type(version) is not int or version != 7 for version in versions):
            errors.append(f"{label}: protocol drift: expected supported v7, found {versions!r}; review contract and checker")
    return errors


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


def parse_as_of(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="regenerate docs/controls.md after validation")
    parser.add_argument("--as-of", type=parse_as_of, default=None,
                        help="evaluate maintenance as of YYYY-MM-DD (default: today); never renew records")
    parser.add_argument("--development", action="store_true",
                        help="warn on calendar-only maintenance expiry; all other checks remain strict")
    args = parser.parse_args(argv)
    if args.development and (args.write or args.as_of is not None):
        parser.error("--development cannot be combined with --write or --as-of")
    try:
        as_of = args.as_of or date.today()
        print(f"Maintenance evaluated as of {as_of}.", flush=True)
        registry = json.loads((ROOT / "docs/control-registry.json").read_text())
        warnings = []
        errors = check_registry(ROOT, registry, as_of=as_of,
                                warnings=warnings if args.development else None)
        for warning in warnings:
            print(f"Governance warning: {warning}", file=sys.stderr, flush=True)
        errors += check_protocol(ROOT) + check_manifests(ROOT)
        if not args.write and not errors:
            errors += check_generated(ROOT, registry)
        if errors:
            raise ValueError("\n".join(errors))
        if args.write:
            (ROOT / "docs/controls.md").write_text(render_map(registry))
            print("Generated docs/controls.md; no gameplay or evidence-byte verification performed.")
        else:
            print("Governance schemas, mappings, local references, current protocol source forms and map freshness: passed.")
        return 0
    except (OSError, ValueError, SyntaxError, SchemaError) as error:
        print(f"Governance failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
