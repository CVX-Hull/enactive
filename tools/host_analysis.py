"""Read-only player-host event analysis; historical omissions remain unknown, not zero."""
from __future__ import annotations

from collections import Counter
import hashlib
import math
from pathlib import Path

from harness.computer.protocol import ControlError, read_json
from harness.evaluation.core.metrics import nearest_rank
from harness.evaluation.core.records import EvaluationError
from harness.evaluation.core.sources import (DRIVER_SCHEMA, MANIFEST_SCHEMA, RECEIPT_SCHEMA, ArchiveSession,
    HostTraceUnsupported, accepted_versions, iter_host, run_archive_entry)

MAX_REQUESTS = 200_000
#: Prompt-size bands in tokens, lower bound inclusive and upper bound exclusive: exactly 20,000 tokens is in the
#: second band and exactly 150,000 in the last. Prompt tokens are `usage.input + usage.cacheRead + usage.cacheWrite`.
PROMPT_BANDS = ((0, 20_000, "under 20,000"), (20_000, 60_000, "20,000 to 60,000"), (60_000, 100_000, "60,000 to 100,000"),
    (100_000, 150_000, "100,000 to 150,000"), (150_000, None, "over 150,000"))
#: A response is "within" a limit when it took at most this many milliseconds.
RESPONSE_LIMITS_MS = {"within_2s": 2000, "within_5s": 5000}
#: A `HostTraceUnsupported.kind` is reported as this coverage.
UNSUPPORTED_COVERAGE = {"empty": "empty", "format": "unsupported_format", "version": "unsupported_version"}


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def distribution(values):
    """`p50` and `p95` are nearest rank (`harness.evaluation.core.metrics.nearest_rank`), the evaluator's definition."""
    items = sorted(value for value in values if number(value))
    if not items:
        return {"n": 0, "sum": None, "p50": None, "p95": None, "max": None}
    return {"n": len(items), "sum": sum(items), "p50": nearest_rank(items, .5), "p95": nearest_rank(items, .95), "max": items[-1]}


def delta(end, start):
    return end - start if number(end) and number(start) and end >= start else None


def prompt_tokens(usage):
    """Input plus cache read plus cache write, or `None` when any of the three is not recorded (unknown, not zero)."""
    parts = [usage.get(key) for key in ("input", "cacheRead", "cacheWrite")] if isinstance(usage, dict) else []
    return sum(parts) if parts and all(number(part) for part in parts) else None


def share_within(values, limit):
    """The fraction of `values` at most `limit`, or `None` for no values."""
    return sum(value <= limit for value in values) / len(values) if values else None


def response_by_prompt(samples, intervals):
    """Response time, by prompt-size band, for completed responses.

    `samples` is a list of `(response_ms, prompt_tokens, cost_usd)`, each part `None` when unknown; `intervals`
    are the milliseconds between the first tool results of consecutive requests. Percentiles are nearest rank
    (`distribution`). A response with no known prompt size counts in the whole but in no band; a response
    with no reported cost counts in the band but not in its mean cost."""
    timed = [(ms, prompt, cost) for ms, prompt, cost in samples if number(ms)]

    def figures(group):
        durations = [ms for ms, _, _ in group]
        costs = [cost for _, _, cost in group if number(cost)]
        return {"response_ms": distribution(durations), **{key: share_within(durations, limit) for key, limit in RESPONSE_LIMITS_MS.items()},
            "mean_cost_usd": sum(costs) / len(costs) if costs else None, "cost_n": len(costs)}

    waits = [value for value in intervals if number(value)]
    return {**figures(timed), "unknown_prompt_responses": sum(not number(prompt) for _, prompt, _ in timed),
        "bands": [{"band": label, "min_tokens": low, "max_tokens": high, **figures([row for row in timed
            if number(row[1]) and row[1] >= low and (high is None or row[1] < high)])} for low, high, label in PROMPT_BANDS],
        "first_tool_result_interval_ms": {**distribution(waits), **{key: share_within(waits, limit) for key, limit in RESPONSE_LIMITS_MS.items()}}}


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


def response_by_requests(rows):
    """`response_by_prompt` over request rows: completed responses only; a censored request is not a sample."""
    rows = list(rows)
    return response_by_prompt([(row["observed_ms"], row["prompt_tokens"], row["cost_usd"]) for row in rows if not row["censored"]],
        [row["since_previous_first_tool_result_ms"] for row in rows])


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


def run_root(path: Path) -> Path:
    """The run directory a trace file sits in: two levels above `actors/NNN/host.jsonl`, else its own directory."""
    return path.parent.parent.parent if path.parent.parent.name == "actors" else path.parent


#: The driver record's totals. A current record adds the counted spend; `configured_estimate_usd` stays an
#: estimate from the route's configured rates.
DRIVER_KEYS = ("schema", "outcome", "attempts_charged", "host_seconds_used", "configured_estimate_usd", "missing_usage_attempts")
DRIVER_SPEND_KEYS = ("reported_usd", "unpriced_requests", "unpriced_request_usd", "spent_usd", "spend_complete")


def campaign_evidence(path: Path, entry: ArchiveSession | None = None) -> dict:
    """The run's sidecars in their current versions, or in the versions the archive index lists for its session
    (`entry`); host completion is never goal acceptance."""
    root = run_root(path)
    result = {"metadata_coverage": {}}
    fields = {
        "manifest.json": (accepted_versions(entry, "manifest", MANIFEST_SCHEMA), ("session", "source_commit")),
        "receipt.json": (accepted_versions(entry, "receipt", RECEIPT_SCHEMA), ("session", "source_commit", "outcome",
            "normal_save_claimed_by_harness", "native_absence_verified", "normal_native_exit_zero",
            "deciding_hosts_quiescent", "input_authority_revoked")),
    }
    for relative, (schemas, keys) in fields.items():
        artifact = root / relative
        coverage = "missing"
        if artifact.exists():
            try:
                value = read_json(artifact, 1024 * 1024)
                if not isinstance(value, dict) or value.get("schema") not in schemas:
                    coverage = "unsupported_version"
                else:
                    result[relative] = {key: value.get(key) for key in keys}
                    coverage = "recorded"
                    if relative == "receipt.json" and value.get("driver") is not None:
                        driver = value["driver"]
                        if not isinstance(driver, dict) or driver.get("schema") not in accepted_versions(entry, "driver", DRIVER_SCHEMA):
                            coverage = "unsupported_driver_version"
                        else:
                            result[relative]["driver"] = {key: driver.get(key) for key in
                                (DRIVER_KEYS + DRIVER_SPEND_KEYS if driver["schema"] == DRIVER_SCHEMA else DRIVER_KEYS)}
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
    if path.is_symlink() or not path.is_file():
        raise ControlError("Select a bounded regular trace file")
    size = path.stat().st_size
    if size > 8 * 1024 ** 3:
        raise ControlError("Select a bounded regular trace file")
    rows, tools, tool_intervals = {}, {}, []
    counts = Counter()
    start = terminal = previous = None
    clock_valid = True
    host_count = 0
    context, config, output_sink = [], {}, None
    abort = None
    # An older trace is read only inside the run directory of a session the closed archive index lists.
    archived = run_archive_entry(run_root(path))
    try:
        for parsed in iter_host(path, path.parent.name, entry=archived):
            event, line_number = parsed.fields, parsed.line
            kind, at = parsed.type, event.get("monotonic_ms")
            counts[kind] += 1
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
                host_count += 1
                if host_count > 1:
                    raise ControlError(f"Multiple hosts in one trace; split at original host boundaries: {path}")
                start = at
                config = {key: event.get(key) for key in ("schema", "model", "provider", "api", "effort",
                    "requested_service_tier", "max_context_images", "context_image_block", "context_reserve_tokens", "max_output_tokens", "context_window", "thinking_level_map", "reasoning_format", "provider_routing", "telemetry_version")}
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
                rows[event["request_id"]].setdefault("first_tool_result_ms", at)
            elif kind == "abort":
                abort = event
            elif kind == "settled":
                terminal = event
                sink = event.get("event_output")
                if sink is not None and not isinstance(sink, dict):
                    raise ControlError("Expected event output metadata")
                output_sink = {key: sink.get(key) if number(sink.get(key)) else None for key in
                    ("events", "callback_ms", "max_callback_ms", "json_ms", "enqueue_ms", "bytes", "backpressure_signals")} if sink else None
    except HostTraceUnsupported as exc:
        return {"path": str(path), "coverage": UNSUPPORTED_COVERAGE[exc.kind], "file_bytes": size}
    with path.open("rb") as stream:
        sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        parsed_bytes = stream.tell()
    if parsed_bytes != size:
        raise ControlError("Trace changed during analysis")
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
        cost = usage.get("cost") if isinstance(usage, dict) else None
        row["prompt_tokens"] = prompt_tokens(usage)
        row["cost_usd"] = cost.get("total") if isinstance(cost, dict) and number(cost.get("total")) else None
        row["usage"] = {key: usage.get(key) if number(usage.get(key)) else None for key in usage_fields} if isinstance(usage, dict) else None
        row["progress"] = progress
    # The interval ends at a request's first tool result and starts at the previous request's, in request order;
    # a request with no tool result neither ends nor starts one.
    previous_result = None
    for row in rows.values():
        row["since_previous_first_tool_result_ms"] = None
        result = row.get("first_tool_result_ms")
        if result is not None:
            if clock_valid:
                row["since_previous_first_tool_result_ms"] = delta(result, previous_result)
            previous_result = result
    observed_requests = union_ms(requests_intervals) if clock_valid else None
    observed_tools = union_ms(tool_intervals) if clock_valid else None
    overlaps = overlap_ms(requests_intervals, tool_intervals) if clock_valid else None
    return {"path": str(path), "coverage": "player_host",
        "file_bytes": size, "sha256": sha256, "parsed_bytes": parsed_bytes, "configuration": config,
        "clock_valid": clock_valid, "terminal": None if terminal is None else
            {key: terminal.get(key) for key in ("ok", "reason", "requests")},
        "host_ms": host_ms if clock_valid else None, "observed_request_ms": observed_requests,
        "observed_tool_ms": observed_tools, "request_tool_overlap_ms": overlaps,
        "request_share": observed_requests / host_ms if clock_valid and host_ms and not overlaps
            and all(row["observed_ms"] is not None for row in rows.values())
            and all(end is not None for _, end in tools.values()) else None,
        "counts": dict(counts), "http_attempts_observed": len(rows), "censored_requests": incomplete,
        "unknown_usage_requests": unknown_usage, "pending_tools": sum(end is None for _, end in tools.values()),
        "completed_response_ms": distribution(durations), "response_by_prompt": response_by_requests(rows.values()),
        "tool_ms": distribution(delta(b, a) if clock_valid else None for a, b in tool_intervals),
        "timing_ms": {key: distribution(value) for key, value in field_times.items()},
        "usage": {key: distribution(value) for key, value in usage_fields.items()},
        "reported_output_per_post_body_second": distribution(rates),
        "context": {key: distribution(x.get(key) for x in context) for key in
            ("projection_ms", "input_images", "omitted_images", "retained_images")},
        "event_output": output_sink, "campaign_evidence": campaign_evidence(path, archived), "requests": list(rows.values())}


def host_summary(paths: list[Path]) -> dict:
    reports = []
    for path in discover(paths):
        try:
            reports.append(analyze_trace(path))
        except (ControlError, EvaluationError, OSError, ValueError, UnicodeError, RecursionError) as exc:
            reports.append({"path": str(path), "coverage": "invalid", "error": str(exc)})
    hosts = [r for r in reports if r["coverage"] == "player_host"]
    by_run = {}
    for r in hosts:
        by_run.setdefault(str(run_root(Path(r["path"]))), []).append(r)
    return {"complete": all(r["coverage"] == "player_host" for r in reports),"schema": "host-analysis/1", "scope": "Diagnostic host intervals and reported tokens; not server inference, attention, useful-goal latency or readiness",
        "units": "milliseconds unless named otherwise; p50 and p95 are nearest rank; reasoning is a subset of output, not added to it; "
            "prompt-size bands are by input plus cache read plus cache write tokens, lower bound inclusive; "
            "'within' is at most 2000 or 5000 ms; costs are provider-reported dollars",
        "coverage": dict(Counter(r["coverage"] for r in reports)),
        "duplicate_content": [[r["path"] for r in reports if r.get("sha256") == sha]
            for sha, count in Counter(r.get("sha256") for r in reports if r.get("sha256")).items() if count > 1],
        # A run is the directory holding `actors/NNN/host.jsonl`; the selection is every selected `player_host` trace.
        "runs": [{"run": run, "traces": len(group), "response_by_prompt": response_by_requests(row for r in group for row in r["requests"])}
            for run, group in sorted(by_run.items())],
        "selection": {"traces": len(hosts), "response_by_prompt": response_by_requests(row for r in hosts for row in r["requests"])},
        "traces": reports}


def markdown(report: dict) -> str:
    lines = ["# Retained host diagnostics", "", report["scope"], "", report["units"], "",
        "| Trace | Coverage | Attempts / censored | Host s | Request share | Median response s | Median tool s | Within 2 s | Within 5 s |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    def fmt(value, scale=1):
        return "unknown" if value is None else f"{value / scale:.3f}"
    def percent(value):
        return "unknown" if value is None else f"{100 * value:.1f}%"
    for row in report["traces"]:
        name = str(Path(row["path"]).relative_to(Path.cwd())) if Path(row["path"]).is_relative_to(Path.cwd()) else row["path"]
        by_prompt = row.get("response_by_prompt", {})
        lines.append(f"| {name} | {row['coverage']} | {row.get('http_attempts_observed', 'unknown')} / {row.get('censored_requests', 'unknown')} | {fmt(row.get('host_ms'), 1000)} | {fmt(row.get('request_share'))} | {fmt(row.get('completed_response_ms', {}).get('p50'), 1000)} | {fmt(row.get('tool_ms', {}).get('p50'), 1000)} | {percent(by_prompt.get('within_2s'))} | {percent(by_prompt.get('within_5s'))} |")

    def seconds(value):
        return "unknown" if value is None else f"{value / 1000:.1f}"

    def timing_row(label, figures, traces=None):
        response = figures["response_ms"]
        cost = "unknown" if figures["mean_cost_usd"] is None else f"{figures['mean_cost_usd']:.4f}"
        cells = [label, *([str(traces)] if traces is not None else []), f"{response['n']:,}", seconds(response["p50"]), seconds(response["p95"]),
            percent(figures["within_2s"]), percent(figures["within_5s"]), cost]
        return "| " + " | ".join(cells) + " |"

    header = "| {} | Responses | Median s | 95th percentile s | Within 2 s | Within 5 s | Mean cost per request $ |"
    divider = "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"
    selection = report["selection"]
    figures = selection["response_by_prompt"]
    lines += ["", f"## Response time by prompt size, {selection['traces']} selected traces", "", "Completed responses only; a response whose prompt size is unknown "
        f"({figures['unknown_prompt_responses']}) is in the first row but in no band.", "", header.format("Prompt tokens"), divider,
        timing_row("All responses", figures), *(timing_row(band["band"].capitalize(), band) for band in figures["bands"])]
    wait = figures["first_tool_result_interval_ms"]
    lines += ["", f"One request's first tool result to the next request's first tool result: {wait['n']:,} intervals, median {seconds(wait['p50'])} s, "
        f"95th percentile {seconds(wait['p95'])} s, within 2 s {percent(wait['within_2s'])}, within 5 s {percent(wait['within_5s'])}."]
    lines += ["", "## Response time by run", "", header.format("Run").replace("| Responses", "| Traces | Responses", 1), "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for run in report["runs"]:
        lines.append(timing_row(Path(run["run"]).name, run["response_by_prompt"], run["traces"]))
    return "\n".join(lines) + "\n"
