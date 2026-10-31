"""Read-only player-host event analysis; historical omissions remain unknown, not zero."""
from __future__ import annotations

from collections import Counter
import json
import hashlib
import math
from pathlib import Path
import statistics

from harness.computer.protocol import ControlError, decode_json, read_json

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
    """Select files, actor directories or campaign directories; never scan siblings."""
    if not 1 <= len(paths) <= 4096:
        raise ControlError("Select between 1 and 4096 paths")
    files = []
    for path in paths:
        if path.is_symlink():
            raise ControlError(f"Symlink trace path: {path}")
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            if (path / "host.jsonl").is_file():
                files.append(path / "host.jsonl")
            actors = path / "actors"
            if actors.is_symlink():
                raise ControlError("Symlink actor directory")
            if actors.is_dir():
                for actor_index, actor in enumerate(actors.iterdir()):
                    if actor_index >= 4096:
                        raise ControlError("Selected actor directory exceeds 4096 entries")
                    if actor.is_symlink():
                        raise ControlError("Symlink actor directory")
                    if (actor / "host.jsonl").is_file():
                        files.append(actor / "host.jsonl")
                    if len(files) > 4096:
                        raise ControlError("Select at most 4096 trace files")
        else:
            raise ControlError(f"Missing trace path: {path}")
    if any(p.is_symlink() for p in files):
        raise ControlError("Symlink trace file")
    resolved = sorted(p.resolve() for p in files)
    if len(set(resolved)) != len(resolved):
        raise ControlError("Duplicate trace path; select each source once")
    if not 1 <= len(resolved) <= 4096:
        raise ControlError("Select between 1 and 4096 trace files")
    if sum(p.stat().st_size for p in resolved) > 8 * 1024 ** 3:
        raise ControlError("Selected trace corpus exceeds 8 GiB; split the invocation")
    return resolved


def campaign_evidence(path: Path) -> dict:
    """Current selected sidecars only; host completion is never goal acceptance."""
    root = path.parent.parent.parent if path.parent.parent.name == "actors" else path.parent
    result = {"metadata_coverage": {}}
    fields = {
        "manifest.json": ("campaign-run/3", ("session", "source_commit")),
        "receipt.json": ("campaign-receipt/2", ("session", "source_commit", "outcome",
            "normal_save_claimed_by_harness", "native_absence_verified", "normal_native_exit_zero",
            "deciding_hosts_quiescent", "input_authority_revoked")),
    }
    for relative, (schema, keys) in fields.items():
        artifact = root / relative
        coverage = "missing"
        if artifact.exists():
            try:
                value = read_json(artifact, 1024 * 1024)
                if not isinstance(value, dict) or value.get("schema") != schema:
                    coverage = "unsupported_version"
                else:
                    result[relative] = {key: value.get(key) for key in keys}
                    coverage = "recorded"
                    if relative == "receipt.json" and value.get("driver") is not None:
                        driver = value["driver"]
                        if not isinstance(driver, dict) or driver.get("schema") != "player-driver/2":
                            coverage = "unsupported_driver_version"
                        else:
                            result[relative]["driver"] = {key: driver.get(key) for key in
                                ("schema", "outcome", "attempts_charged", "host_seconds_used",
                                 "configured_estimate_usd", "missing_usage_attempts")}
            except (ValueError, OSError, UnicodeError, RecursionError):
                coverage = "invalid"
        result["metadata_coverage"][relative] = coverage
    return result


PROGRESS_NUMBERS = ("body_bytes", "body_chunks", "provider_events", "content_bytes", "reasoning_bytes",
    "tool_argument_bytes", *(f"{prefix}_{group}_{suffix}" for group in
    ("body_chunk", "provider_event", "field_delta", "reasoning_delta", "content_delta", "tool_argument_delta")
    for prefix, suffix in (("first", "ms"), ("last", "ms"), ("max", "gap_ms"))))


def progress_metadata(value: dict | None) -> dict:
    # Provider fields and tool payloads are not copied into the diagnostic output.
    return {key: value.get(key) if number(value.get(key)) else None for key in PROGRESS_NUMBERS} if value else {}


def analyze_trace(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 ** 3:
        raise ControlError("Select a bounded regular trace file")
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
                raise ControlError(f"Trace line exceeds 64 MiB: {path}:{line_number}")
            try:
                event = decode_json(line, MAX_LINE_BYTES)
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise ControlError(f"Malformed trace JSON: {path}:{line_number}") from exc
            if not isinstance(event, dict):
                raise ControlError(f"Expected event object: {path}:{line_number}")
            kind, at = event.get("type"), event.get("monotonic_ms")
            if line_number == 1 and kind != "host-start":
                return {"path": str(path), "coverage": "unsupported_format", "file_bytes": path.stat().st_size}
            counts[kind if isinstance(kind, str) else "missing_type"] += 1
            if terminal is not None:
                raise ControlError(f"Event after host settlement: {path}:{line_number}")
            if kind in ("request-fetch-start", "response-headers", "response-first-chunk", "response-complete", "provider-refusal", "tool-start", "tool-result"):
                if not isinstance(event.get("request_id"), str):
                    raise ControlError(f"Expected request identity: {path}:{line_number}")
            if "response_progress" in event and event["response_progress"] is not None and not isinstance(event["response_progress"], dict):
                raise ControlError(f"Expected progress object: {path}:{line_number}")
            if not number(at) or previous is not None and at < previous:
                clock_valid = False
            if number(at):
                previous = at
            if kind == "host-start":
                if event.get("schema") != "player-host/2" or type(event.get("telemetry_version")) is not int or event["telemetry_version"] != 2:
                    return {"path": str(path), "coverage": "unsupported_version", "file_bytes": path.stat().st_size}
                host_count += 1
                if host_count > 1:
                    raise ControlError(f"Multiple hosts in one trace; split at original host boundaries: {path}")
                start = at
                config = {key: event.get(key) for key in ("schema", "model", "provider", "api", "effort",
                    "requested_service_tier", "max_context_images", "context_image_block", "max_output_tokens", "context_window", "thinking_level_map", "reasoning_format", "provider_routing", "telemetry_version")}
            elif kind == "context-image-projection":
                context.append({key: event.get(key) for key in ("projection_ms", "input_images", "omitted_images", "retained_images")})
            elif kind == "request-start":
                identity = event.get("request_id")
                if not isinstance(identity, str) or not identity or identity in rows or len(rows) >= MAX_REQUESTS:
                    raise ControlError(f"Invalid/duplicate request identity or request bound: {path}:{line_number}")
                rows[identity] = {"request_id": identity, "start_ms": at,
                    **{key: event.get(key) for key in ("logical_request_id", "payload_bytes", "text_bytes", "image_parts",
                        "image_bytes", "host_inspection_ms", "sdk_after_payload_ms")}}
            elif kind in ("request-fetch-start", "response-headers", "response-first-chunk", "response-complete", "provider-refusal"):
                row = rows.get(event.get("request_id"))
                if row is None:
                    raise ControlError(f"Response lacks original request: {path}:{line_number}")
                field = {"request-fetch-start": "fetch_ms", "response-headers": "headers_ms",
                    "response-first-chunk": "first_body_ms", "response-complete": "end_ms", "provider-refusal": "refusal_ms"}[kind]
                if field in row:
                    raise ControlError(f"Duplicate request endpoint: {path}:{line_number}")
                row[field] = at
                if kind == "response-headers":
                    row["http_status"] = event.get("status")
                elif kind == "provider-refusal":
                    row["error_type"], row["error_code"] = event.get("error_type"), event.get("error_code")
                    row["limit_source"], row["provider_error_code"] = event.get("limit_source"), event.get("provider_error_code")
                elif kind == "response-complete":
                    row["stop_reason"] = event.get("stop_reason")
                    row["usage"] = event.get("usage") if event.get("usage_available") is True else None
                    row["cost_source"] = event.get("cost_source")
                    row["progress"] = progress_metadata(event.get("response_progress"))
            elif kind == "tool-start":
                identity = (event.get("request_id"), event.get("tool_call_id"))
                if not all(isinstance(x, str) and x for x in identity) or identity in tools or identity[0] not in rows:
                    raise ControlError(f"Invalid/duplicate tool identity: {path}:{line_number}")
                tools[identity] = [at, None]
            elif kind == "tool-result":
                if not isinstance(event.get("tool_call_id"), str):
                    raise ControlError(f"Expected tool identity: {path}:{line_number}")
                entry = tools.get((event.get("request_id"), event.get("tool_call_id")))
                if entry is None or entry[1] is not None:
                    raise ControlError(f"Unpaired/duplicate tool result: {path}:{line_number}")
                entry[1] = at
                tool_intervals.append(tuple(entry))
            elif kind == "abort":
                abort = event
            elif kind == "settled":
                terminal = event
                sink = event.get("event_output")
                if sink is not None and not isinstance(sink, dict):
                    raise ControlError("Expected event output metadata")
                output_sink = {key: sink.get(key) if number(sink.get(key)) else None for key in
                    ("events", "callback_ms", "max_callback_ms", "json_ms", "enqueue_ms", "bytes", "backpressure_signals")} if sink else None
        else:
            raise ControlError(f"Trace exceeds two million events: {path}")
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
            progress = progress_metadata(abort.get("response_progress"))
        row["censored"] = "end_ms" not in row or row.get("stop_reason") not in ("stop", "toolUse")
        incomplete += row["censored"]
        duration = delta(end, row["start_ms"]) if clock_valid else None
        row["observed_ms"] = duration
        if duration is not None:
            requests_intervals.append((row["start_ms"], end))
            if not row["censored"]:
                durations.append(duration)
        base = row.get("fetch_ms")
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
        row["usage"] = {key: usage.get(key) if number(usage.get(key)) else None for key in usage_fields} if isinstance(usage, dict) else None
        row["progress"] = progress
    observed_requests = union_ms(requests_intervals) if clock_valid else None
    observed_tools = union_ms(tool_intervals) if clock_valid else None
    overlaps = overlap_ms(requests_intervals, tool_intervals) if clock_valid else None
    return {"path": str(path), "coverage": "player_host",
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
    for path in discover(paths):
        try:
            reports.append(analyze_trace(path))
        except (ControlError, OSError, ValueError, UnicodeError, RecursionError) as exc:
            reports.append({"path": str(path), "coverage": "invalid", "error": str(exc)})
    return {"complete": all(r["coverage"] == "player_host" for r in reports),"schema": "host-analysis/1", "scope": "Diagnostic host intervals and reported tokens; not server inference, attention, useful-goal latency or readiness",
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
