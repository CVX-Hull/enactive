"""Read-only Pi event analysis; historical omissions remain unknown, not zero."""
from __future__ import annotations

from collections import Counter
import json
import hashlib
import math
from pathlib import Path
import statistics

from harness.gameplay.contracts import ContractError, _pairs, _reject_constant

MAX_LINE_BYTES = 64 * 1024 * 1024
MAX_REQUESTS = 200_000


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def distribution(values):
    items = sorted(value for value in values if number(value))
    if not items:
        return {"n": 0, "sum": None, "p50": None, "p95": None, "max": None}
    return {"n": len(items), "sum": sum(items), "p50": statistics.median(items),
            "p95": items[math.ceil(.95 * len(items)) - 1], "max": items[-1]}


def delta(end, start):
    return end - start if number(end) and number(start) and end >= start else None


def merged_intervals(intervals):
    ordered = sorted((a, b) for a, b in intervals if number(a) and number(b) and b >= a)
    merged = []
    for a, b in ordered:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def union_ms(intervals):
    return sum(b - a for a, b in merged_intervals(intervals))


def overlap_ms(first, second):
    # Intersect endpoints directly: subtracting three floating point union sums
    # can invent a tiny overlap even for strictly sequential request/tool work.
    left, right = merged_intervals(first), merged_intervals(second)
    i = j = 0
    total = 0
    while i < len(left) and j < len(right):
        a, b = left[i]
        c, d = right[j]
        total += max(0, min(b, d) - max(a, c))
        if b <= d:
            i += 1
        else:
            j += 1
    return total


def discover(paths: list[Path]) -> list[Path]:
    """Known evidence locations only; never recursively parse all runtime JSON."""
    files = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            # Accept a campaign or a directory containing campaigns.
            dirs = [path, *sorted(p for p in path.iterdir() if p.is_dir())]
            selected = set()
            for directory in dirs:
                for pattern in ("driver-*.jsonl", "*-active.jsonl", "evidence/host-traces/*.jsonl"):
                    selected.update(directory.glob(pattern))
            files.extend(sorted(selected))
        else:
            raise ContractError(f"Missing trace path: {path}")
    resolved = [p.resolve() for p in files]
    if len(set(resolved)) != len(resolved):
        raise ContractError("Duplicate trace path; select each source once")
    if not resolved or len(resolved) > 4096:
        raise ContractError("Select between 1 and 4096 trace files")
    return resolved


def campaign_evidence(path: Path) -> dict:
    """Declared sidecar provenance/disposition, never acceptance inferred from host0."""
    result = {"metadata_coverage": {}}
    root = path.parent.parent.parent if path.parent.name == "host-traces" and path.parent.parent.name == "evidence" else path.parent
    fields = {
        "frozen/manifest.json": ("source_commit", "source", "mission_id"),
        "frozen/player-pi-configuration.json": ("model",),
        "preparation/driver-report.json": ("outcome", "phase", "exit_code"),
        "preparation/custodian-receipt.json": ("outcome", "normal_ending_claimed", "native_absence_verified", "signals"),
    }
    for relative, keys in fields.items():
        source = root / relative
        coverage = "missing"
        if source.is_file():
            with source.open("rb") as stream:
                data = stream.read(1024 * 1024 + 1)
            coverage = "empty" if not data else "invalid"
            if data and len(data) <= 1024 * 1024:
                try:
                    value = json.loads(data, object_pairs_hook=_pairs, parse_constant=_reject_constant)
                    if isinstance(value, dict):
                        if relative.endswith("player-pi-configuration.json"):
                            model = value.get("model")
                            if not isinstance(model, dict):
                                raise ValueError("Missing frozen model")
                            result[relative] = {key: model.get(key) for key in
                                ("id", "contextWindow", "maxTokens", "thinkingLevelMap")}
                        else:
                            result[relative] = {key: value.get(key) for key in keys}
                        coverage = "recorded"
                except (ValueError, UnicodeError, AttributeError, RecursionError):
                    pass
        result["metadata_coverage"][relative] = coverage
    return result


def analyze_trace(path: Path) -> dict:
    rows, tools, tool_intervals = {}, {}, []
    counts = Counter()
    start = terminal = previous = None
    clock_valid = True
    host_count = 0
    context, config, output_sink = [], {}, None
    abort = None
    parsed_bytes = 0
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for line_number in range(1, 2_000_001):
            line = stream.readline(MAX_LINE_BYTES + 1)
            if not line:
                break
            parsed_bytes += len(line)
            digest.update(line)
            if len(line) > MAX_LINE_BYTES:
                raise ContractError(f"Trace line exceeds 64 MiB: {path}:{line_number}")
            try:
                event = json.loads(line, object_pairs_hook=_pairs, parse_constant=_reject_constant)
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise ContractError(f"Malformed trace JSON: {path}:{line_number}") from exc
            if not isinstance(event, dict):
                raise ContractError(f"Expected event object: {path}:{line_number}")
            kind, at = event.get("type"), event.get("monotonic_ms")
            if line_number == 1 and kind not in ("host-start", "abort", "settled"):
                return {"path": str(path), "coverage": "unsupported_format", "file_bytes": path.stat().st_size}
            counts[kind if isinstance(kind, str) else "missing_type"] += 1
            if terminal is not None:
                raise ContractError(f"Event after host settlement: {path}:{line_number}")
            if kind in ("request-fetch-start", "response-headers", "response-first-chunk", "response-complete", "provider-refusal", "tool-start", "tool-result"):
                if not isinstance(event.get("request_id"), str):
                    raise ContractError(f"Expected request identity: {path}:{line_number}")
            if "response_progress" in event and event["response_progress"] is not None and not isinstance(event["response_progress"], dict):
                raise ContractError(f"Expected progress object: {path}:{line_number}")
            if not number(at) or previous is not None and at < previous:
                clock_valid = False
            if number(at):
                previous = at
            if kind == "host-start":
                if event.get("schema") not in (None, "pi-player-host/1", "pi-player-host/2", "pi-player-host/3", "pi-player-host/4") or event.get("telemetry_version") not in (None, 1):
                    return {"path": str(path), "coverage": "unsupported_version", "file_bytes": path.stat().st_size}
                host_count += 1
                if host_count > 1:
                    raise ContractError(f"Multiple hosts in one trace; split at original host boundaries: {path}")
                start = at
                config = {key: event.get(key) for key in ("schema", "model", "provider", "api", "effort",
                    "requested_service_tier", "max_context_images", "max_output_tokens", "context_window", "thinking_level_map", "reasoning_format", "provider_routing", "telemetry_version")}
            elif kind == "context-image-projection":
                context.append({key: event.get(key) for key in ("projection_ms", "input_images", "omitted_images", "retained_images")})
            elif kind == "request-start":
                identity = event.get("request_id")
                if not isinstance(identity, str) or not identity or identity in rows or len(rows) >= MAX_REQUESTS:
                    raise ContractError(f"Invalid/duplicate request identity or request bound: {path}:{line_number}")
                rows[identity] = {"request_id": identity, "start_ms": at,
                    **{key: event.get(key) for key in ("logical_request_id", "payload_bytes", "text_bytes", "image_parts",
                        "image_bytes", "host_inspection_ms", "sdk_after_payload_ms")}}
            elif kind in ("request-fetch-start", "response-headers", "response-first-chunk", "response-complete", "provider-refusal"):
                row = rows.get(event.get("request_id"))
                if row is None:
                    raise ContractError(f"Response lacks original request: {path}:{line_number}")
                field = {"request-fetch-start": "fetch_ms", "response-headers": "headers_ms",
                    "response-first-chunk": "first_body_ms", "response-complete": "end_ms", "provider-refusal": "refusal_ms"}[kind]
                if field in row:
                    raise ContractError(f"Duplicate request endpoint: {path}:{line_number}")
                row[field] = at
                if kind == "response-headers":
                    row["http_status"] = event.get("status")
                elif kind == "provider-refusal":
                    row["error_type"], row["error_code"] = event.get("error_type"), event.get("error_code")
                elif kind == "response-complete":
                    row["stop_reason"] = event.get("stop_reason")
                    row["usage"] = event.get("usage") if event.get("usage_available") is True else None
                    row["cost_source"] = event.get("cost_source")
                    row["progress"] = event.get("response_progress")
            elif kind == "tool-start":
                identity = (event.get("request_id"), event.get("tool_call_id"))
                if not all(isinstance(x, str) and x for x in identity) or identity in tools or identity[0] not in rows:
                    raise ContractError(f"Invalid/duplicate tool identity: {path}:{line_number}")
                tools[identity] = [at, None]
            elif kind == "tool-result":
                if not isinstance(event.get("tool_call_id"), str):
                    raise ContractError(f"Expected tool identity: {path}:{line_number}")
                entry = tools.get((event.get("request_id"), event.get("tool_call_id")))
                if entry is None or entry[1] is not None:
                    raise ContractError(f"Unpaired/duplicate tool result: {path}:{line_number}")
                entry[1] = at
                tool_intervals.append(tuple(entry))
            elif kind == "abort":
                abort = event
            elif kind == "settled":
                terminal = event
                output_sink = event.get("event_output")
        else:
            raise ContractError(f"Trace exceeds two million events: {path}")
    if not counts:
        return {"path": str(path), "coverage": "empty", "file_bytes": path.stat().st_size}
    host_ms = delta(terminal.get("monotonic_ms"), start) if terminal else None
    durations, rates, requests_intervals = [], [], []
    field_times = {key: [] for key in ("headers", "first_body", "first_reasoning", "first_content", "first_tool_argument",
        "max_body_gap", "max_semantic_gap", "host_inspection", "sdk_after_payload")}
    usage_fields = {key: [] for key in ("input", "output", "reasoning", "cacheRead", "cacheWrite")}
    incomplete = unknown_usage = 0
    for row in rows.values():
        progress = row.get("progress") if isinstance(row.get("progress"), dict) else {}
        end = row.get("end_ms")
        # An aborted interval is observed/censored, never a completed success sample.
        if end is None and abort and abort.get("request_id") == row["request_id"]:
            end = abort.get("monotonic_ms")
            progress = abort.get("response_progress") or {}
        row["censored"] = "end_ms" not in row or row.get("stop_reason") not in ("stop", "toolUse")
        incomplete += row["censored"]
        duration = delta(end, row["start_ms"]) if clock_valid else None
        row["observed_ms"] = duration
        if duration is not None:
            requests_intervals.append((row["start_ms"], end))
            if not row["censored"]:
                durations.append(duration)
        base = row.get("fetch_ms", row["start_ms"])
        for key, endpoint in (("headers", row.get("headers_ms")), ("first_body", row.get("first_body_ms")),
                ("first_reasoning", progress.get("first_reasoning_delta_ms")),
                ("first_content", progress.get("first_content_delta_ms")),
                ("first_tool_argument", progress.get("first_tool_argument_delta_ms"))):
            field_times[key].append(delta(endpoint, base) if clock_valid else None)
        for key, value in (("max_body_gap", progress.get("max_body_chunk_gap_ms")),
                ("max_semantic_gap", progress.get("max_field_delta_gap_ms")),
                ("host_inspection", row.get("host_inspection_ms")), ("sdk_after_payload", row.get("sdk_after_payload_ms"))):
            field_times[key].append(value if clock_valid else None)
        usage = row.get("usage")
        if not isinstance(usage, dict):
            unknown_usage += 1
        else:
            for key in usage_fields:
                usage_fields[key].append(usage.get(key))
            post_body = delta(end, row.get("first_body_ms")) if clock_valid else None
            if not row["censored"] and post_body and number(usage.get("output")):
                rate = usage["output"] * 1000 / post_body
                row["reported_output_per_post_body_second"] = rate
                rates.append(rate)
        row["usage"] = {key: usage.get(key) for key in usage_fields} if isinstance(usage, dict) else None
        row["progress"] = progress
    observed_requests = union_ms(requests_intervals) if clock_valid else None
    observed_tools = union_ms(tool_intervals) if clock_valid else None
    overlaps = overlap_ms(requests_intervals, tool_intervals) if clock_valid else None
    return {"path": str(path), "coverage": "pi_host" if host_count else "runner_only",
        "file_bytes": path.stat().st_size, "sha256": digest.hexdigest(), "parsed_bytes": parsed_bytes, "configuration": config,
        "clock_valid": clock_valid, "terminal": None if terminal is None else
            {key: terminal.get(key) for key in ("ok", "reason", "requests")},
        "host_ms": host_ms if clock_valid else None, "observed_request_ms": observed_requests,
        "observed_tool_ms": observed_tools, "request_tool_overlap_ms": overlaps,
        "request_share": observed_requests / host_ms if clock_valid and host_ms and not overlaps
            and all(row["observed_ms"] is not None for row in rows.values())
            and all(end is not None for _, end in tools.values()) else None,
        "counts": dict(counts), "http_attempts_observed": len(rows), "censored_requests": incomplete,
        "unknown_usage_requests": unknown_usage, "pending_tools": sum(end is None for _, end in tools.values()),
        "completed_response_ms": distribution(durations),
        "tool_ms": distribution(delta(b, a) if clock_valid else None for a, b in tool_intervals),
        "timing_ms": {key: distribution(value) for key, value in field_times.items()},
        "usage": {key: distribution(value) for key, value in usage_fields.items()},
        "reported_output_per_post_body_second": distribution(rates),
        "context": {key: distribution(x.get(key) for x in context) for key in
            ("projection_ms", "input_images", "omitted_images", "retained_images")},
        "event_output": output_sink, "campaign_evidence": campaign_evidence(path), "requests": list(rows.values())}


def host_summary(paths: list[Path]) -> dict:
    reports = []
    selected_bytes = 0
    for path in discover(paths):
        try:
            selected_bytes += path.stat().st_size
            if selected_bytes > 8 * 1024 ** 3:
                raise ContractError("Selected trace corpus exceeds 8 GiB; split the invocation")
            reports.append(analyze_trace(path))
        except (ContractError, OSError) as exc:
            reports.append({"path": str(path), "coverage": "invalid", "error": str(exc)})
    return {"complete": not any(r["coverage"] == "invalid" for r in reports),"schema": "host-analysis/1", "scope": "Diagnostic host intervals and reported tokens; not server inference, attention, useful-goal latency or readiness",
        "units": "milliseconds unless named otherwise; p95 is nearest rank; reasoning is a subset of output, not added to it",
        "coverage": dict(Counter(r["coverage"] for r in reports)),
        "duplicate_content": [[r["path"] for r in reports if r.get("sha256") == sha]
            for sha, count in Counter(r.get("sha256") for r in reports if r.get("sha256")).items() if count > 1],
        "traces": reports}


def markdown(report: dict) -> str:
    lines = ["# Retained host diagnostics", "", report["scope"], "", report["units"], "",
        "| Trace | Coverage | Attempts / censored | Host s | Request share | Median response s | Median tool s |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    def fmt(value, scale=1):
        return "unknown" if value is None else f"{value / scale:.3f}"
    for row in report["traces"]:
        name = str(Path(row["path"]).relative_to(Path.cwd())) if Path(row["path"]).is_relative_to(Path.cwd()) else row["path"]
        lines.append(f"| {name} | {row['coverage']} | {row.get('http_attempts_observed', 'unknown')} / {row.get('censored_requests', 'unknown')} | {fmt(row.get('host_ms'), 1000)} | {fmt(row.get('request_share'))} | {fmt(row.get('completed_response_ms', {}).get('p50'), 1000)} | {fmt(row.get('tool_ms', {}).get('p50'), 1000)} |")
    return "\n".join(lines) + "\n"
