"""Deterministic diagnostic fixtures; no provider, native or quality qualification."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from harness.computer.protocol import ControlError
from harness.evaluation.core.metrics import nearest_rank
from harness.evaluation.core.records import EvaluationError
from harness.evaluation.core.sources import iter_host, read_host
from tools.host_analysis import analyze_trace, discover, distribution, host_summary, markdown


class HostAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def trace(self, events, name="driver-original.jsonl"):
        p = self.root / name
        p.write_text("".join(json.dumps(x) + "\n" for x in events))
        return p

    def event(self, kind, at, **fields):
        if kind == "host-start":
            fields = {"schema": "player-host/4", "telemetry_version": 4, **fields}
        return dict(type=kind, monotonic_ms=at, **fields)

    def test_retries_censoring_and_reasoning_are_not_success_or_extra_tokens(self):
        e = self.event
        events = [e("host-start", 0, model="fixture"), e("request-start", 10, request_id="r1"),
            e("response-complete", 20, request_id="r1", stop_reason="error", usage_available=False),
            e("request-start", 30, request_id="r2"), e("response-first-chunk", 40, request_id="r2"),
            e("response-complete", 140, request_id="r2", stop_reason="toolUse", usage_available=True,
                usage=dict(input=20, cacheRead=80, output=10, reasoning=8)),
            e("tool-start", 141, request_id="r2", tool_call_id="same"),
            e("tool-result", 151, request_id="r2", tool_call_id="same"),
            e("request-start", 160, request_id="r3"), e("abort", 180, request_id="r3"),
            e("settled", 190, ok=False, reason="cancelled", requests=3)]
        row = analyze_trace(self.trace(events))
        self.assertEqual(row["http_attempts_observed"], 3)
        self.assertEqual(row["censored_requests"], 2)
        self.assertEqual(row["unknown_usage_requests"], 2)
        self.assertEqual(row["usage"]["output"]["sum"], 10)
        self.assertEqual(row["usage"]["reasoning"]["sum"], 8)
        self.assertEqual(row["reported_output_per_post_body_second"]["p50"], 100)
        self.assertEqual(row["completed_response_ms"]["n"], 1)
        self.assertEqual(row["observed_request_ms"], 140)
        self.assertEqual(row["timing_ms"]["first_reasoning"]["n"], 0)
        self.assertEqual(row["pending_tools"], 0)

    def test_p50_is_nearest_rank_not_the_mean_of_the_middle_pair(self):
        e = self.event
        events = [e("host-start", 0), e("request-start", 10, request_id="r1"),
            e("response-complete", 110, request_id="r1", stop_reason="stop"),
            e("request-start", 200, request_id="r2"), e("response-complete", 500, request_id="r2", stop_reason="stop"),
            e("settled", 600)]
        row = analyze_trace(self.trace(events))
        self.assertEqual(row["completed_response_ms"]["n"], 2)
        self.assertEqual((row["completed_response_ms"]["p50"], row["completed_response_ms"]["p95"]), (100, 300))
        values = [4, 1, 3, 2]
        self.assertEqual(distribution(values)["p50"], nearest_rank(values, .5))
        self.assertEqual((distribution(values)["p50"], distribution(values)["p95"]), (2, 4))
        self.assertEqual(distribution([5])["p50"], 5)

    def test_the_trace_is_parsed_by_the_evaluator_parser(self):
        e = self.event
        path = self.trace([e("host-start", 0), e("request-start", 10, request_id="r1"),
            e("response-complete", 20, request_id="r1", stop_reason="stop"), e("settled", 30)])
        text = path.read_text().split("\n")
        path.write_text("\n".join([text[0], "", *text[1:]]))  # a blank line: skipped by the one parser
        row = analyze_trace(path)
        self.assertEqual(sum(row["counts"].values()), len(read_host(path, "x")[1]))
        with mock.patch("harness.evaluation.core.sources.MAX_HOST_LINE_BYTES", 64):  # its bounds are host-summary's bounds
            self.assertEqual(host_summary([path])["coverage"], dict(invalid=1))
        with mock.patch("harness.evaluation.core.sources.MAX_HOST_EVENTS", 2):
            self.assertEqual(host_summary([path])["coverage"], dict(invalid=1))
        with path.open("a") as stream:
            stream.write('{"type":')
        self.assertEqual(len(read_host(path, "x")[1]), 4)  # the evaluator ignores a line still being appended
        self.assertEqual(host_summary([path])["coverage"], dict(invalid=1))  # a retained trace must be whole

    def test_the_parser_edge_cases_are_pinned(self):
        e = self.event
        # An integer beyond the float range is not a clock reading; it must not crash the parser.
        huge = self.trace([e("host-start", 10 ** 400)], "huge.jsonl")
        self.assertIsNone(read_host(huge, "x")[1][0].monotonic_ms)
        # A second host-start of another version is invalid, not an unsupported trace.
        second = self.trace([e("host-start", 0), e("host-start", 1, schema="player-host/2")], "second.jsonl")
        self.assertEqual(host_summary([second])["coverage"], dict(invalid=1))
        # A later event without a string type is invalid.
        for bad in (dict(monotonic_ms=1), dict(type=7, monotonic_ms=1)):
            typeless = self.trace([e("host-start", 0), bad], "typeless.jsonl")
            self.assertEqual(host_summary([typeless])["coverage"], dict(invalid=1))
            with self.assertRaises(EvaluationError):
                read_host(typeless, "x")
        # A duplicate key on a later line is rejected by the shared parser, not only on the first line.
        duplicate = self.root / "duplicate.jsonl"
        duplicate.write_text(json.dumps(e("host-start", 0)) + '\n{"type":"settled","type":"abort"}\n')
        self.assertEqual(host_summary([duplicate])["coverage"], dict(invalid=1))
        with self.assertRaises(EvaluationError):
            read_host(duplicate, "x")
        # Only blank lines is an empty trace; the event bound counts lines and accepts exactly the bound.
        blank = self.root / "blank.jsonl"
        blank.write_text("\n\n")
        self.assertEqual(host_summary([blank])["coverage"], dict(empty=1))
        four = self.trace([e("host-start", 0), e("request-start", 1, request_id="r"), e("abort", 2), e("settled", 3)], "four.jsonl")
        with mock.patch("harness.evaluation.core.sources.MAX_HOST_EVENTS", 4):
            self.assertEqual(host_summary([four])["coverage"], dict(player_host=1))
        with mock.patch("harness.evaluation.core.sources.MAX_HOST_EVENTS", 3):
            self.assertEqual(host_summary([four])["coverage"], dict(invalid=1))

    def test_a_trace_that_grows_during_analysis_is_refused(self):
        e = self.event
        path = self.trace([e("host-start", 0), e("settled", 1)])
        parse = iter_host

        def growing(*args, **kwargs):
            yield from parse(*args, **kwargs)
            with path.open("a") as stream:
                stream.write("\n")
        with mock.patch("tools.host_analysis.iter_host", growing):
            with self.assertRaisesRegex(ControlError, "changed during analysis"):
                analyze_trace(path)

    def test_context_manifest_is_not_a_request_or_an_attempt(self):
        e = self.event
        events = [e("host-start", 0), e("request-start", 10, request_id="r1"),
            e("context-manifest", 11, request_id="r1", base_request_id=None, reused_prefix_parts=0, part_count=0, parts=[]),
            e("request-fetch-start", 12, request_id="r1"),
            e("response-complete", 20, request_id="r1", stop_reason="stop", usage_available=False), e("settled", 30)]
        row = analyze_trace(self.trace(events))
        self.assertEqual(row["http_attempts_observed"], 1)
        self.assertEqual(row["counts"]["context-manifest"], 1)

    def test_actor_directory_selects_current_trace_and_explicit_duplicates_refuse(self):
        path = self.trace([self.event("host-start", 0)], "host.jsonl")
        self.assertEqual(discover([self.root]), [path.resolve()])
        with self.assertRaises(ControlError):
            discover([self.root, path])

    def test_clock_regression_censors_all_durations(self):
        e = self.event
        row = analyze_trace(self.trace([e("host-start", 0), e("request-start", 10, request_id="r"),
            e("response-complete", 9, request_id="r", stop_reason="stop"), e("settled", 20)]))
        self.assertFalse(row["clock_valid"])
        self.assertIsNone(row["request_share"])
        self.assertIsNone(row["host_ms"])
        self.assertEqual(row["completed_response_ms"]["n"], 0)
        self.assertEqual(row["response_by_prompt"]["response_ms"]["n"], 0)
        huge =analyze_trace(self.trace([e("host-start", 10 ** 400)]))
        self.assertFalse(huge["clock_valid"])

    def test_duplicate_fields_and_nonfinite_json_are_invalid(self):
        path = self.root / "bad.jsonl"
        for raw in ('{"type":"host-start","type":"settled"}', '{"type":"host-start","monotonic_ms":NaN}'):
            path.write_text(raw + "\n")
            self.assertEqual(host_summary([path])["coverage"], dict(invalid=1))

    def test_empty_unsupported_duplicate_and_partial_traces_remain_visible(self):
        empty = self.trace([], "empty.jsonl")
        unknown = self.trace([dict(type="thread.started")], "legacy.jsonl")
        bad = self.trace([self.event("host-start", 0)], "partial.jsonl")
        with bad.open("a") as stream:
            stream.write('{"type":')
        report = host_summary([empty, unknown, bad])
        self.assertEqual(report["coverage"], dict(empty=1, unsupported_format=1, invalid=1))
        self.assertFalse(report["complete"])
        with self.assertRaises(ControlError):
            discover([empty, empty])

    def test_unversioned_early_abort_and_future_telemetry_are_not_interpreted(self):
        e = self.event
        row = analyze_trace(self.trace([e("abort", 0, reason="cancelled"), e("settled", 1, reason="cancelled", ok=False)]))
        self.assertEqual(row["coverage"], "unsupported_format")
        row = analyze_trace(self.trace([e("host-start", 0, telemetry_version=999)]))
        self.assertEqual(row["coverage"], "unsupported_version")

    def test_overlapping_request_and_tool_intervals_do_not_claim_time_share(self):
        e = self.event
        row = analyze_trace(self.trace([e("host-start", 0), e("request-start", 1, request_id="r"),
            e("tool-start", 2, request_id="r", tool_call_id="t"), e("tool-result", 3, request_id="r", tool_call_id="t"),
            e("response-complete", 5, request_id="r", stop_reason="stop"), e("settled", 6)]))
        self.assertEqual(row["request_tool_overlap_ms"], 1)
        self.assertIsNone(row["request_share"])

    def test_sequential_fractional_intervals_have_no_roundoff_overlap(self):
        e = self.event
        row = analyze_trace(self.trace([e("host-start", .001), e("request-start", .123, request_id="r"),
            e("response-complete", 1234.9876543, request_id="r", stop_reason="stop"),
            e("tool-start", 1234.9876544, request_id="r", tool_call_id="t"),
            e("tool-result", 1235.1345678, request_id="r", tool_call_id="t"), e("settled", 1236.1)]))
        self.assertEqual(row["request_tool_overlap_ms"], 0)
        self.assertIsNotNone(row["request_share"])

    def test_unknown_stop_reason_and_missing_interval_never_become_completed_or_zero_share(self):
        e = self.event
        for reason in (None, "new-future-reason"):
            row = analyze_trace(self.trace([e("host-start", 0), e("request-start", 1, request_id="r"),
                e("response-complete", 10, request_id="r", stop_reason=reason), e("settled", 11)]))
            self.assertEqual(row["completed_response_ms"]["n"], 0)
            self.assertEqual(row["censored_requests"], 1)
        row = analyze_trace(self.trace([e("host-start", 0), e("request-start", 1, request_id="r"), e("settled", 11)]))
        self.assertIsNone(row["request_share"])

    def test_malformed_nested_host_shapes_report_invalid(self):
        e = self.event
        for event in (e("response-headers", 2, request_id=[]),
                e("abort", 2, request_id="r", response_progress=["bad"]),
                e("tool-result", 2, request_id="r", tool_call_id=[])):
            path = self.trace([e("host-start", 0), e("request-start", 1, request_id="r"), event])
            self.assertEqual(host_summary([path])["coverage"], dict(invalid=1))

    def test_duplicate_endpoints_fail_and_counts_are_not_independent_goals(self):
        e = self.event
        path = self.trace([e("host-start", 0), e("request-start", 1, request_id="r"), e("request-start", 2, request_id="r")])
        self.assertEqual(host_summary([path])["coverage"], dict(invalid=1))

    def test_only_exact_current_host_version_is_interpreted(self):
        # A loose trace has no archived session: the version the dollar limit replaced is refused like any other.
        for fields in ({}, {"schema": "pi-player-host/4", "telemetry_version": 2},
                       {"schema": "player-host/1", "telemetry_version": 2},
                       {"schema": "player-host/3", "telemetry_version": 3},
                       {"schema": "player-host/3", "telemetry_version": 4},
                       {"schema": "player-host/4", "telemetry_version": 3},
                       {"schema": "player-host/4", "telemetry_version": 1},
                       {"schema": "player-host/4", "telemetry_version": True}):
            row = analyze_trace(self.trace([dict(type="host-start", monotonic_ms=0, **fields)]))
            self.assertEqual(row["coverage"], "unsupported_version")
            self.assertNotIn("requests", row)

    def test_image_policy_counts_are_captured_with_the_configuration(self):
        e = self.event
        row = analyze_trace(self.trace([e("host-start", 0, max_context_images=39, context_image_block=10)]))
        self.assertEqual((row["configuration"]["max_context_images"], row["configuration"]["context_image_block"]), (39, 10))

    def test_progress_times_remain_relative_to_original_fetch_and_payload_is_omitted(self):
        e = self.event
        progress = dict(first_reasoning_delta_ms=25, first_content_delta_ms=40,
                        first_tool_argument_delta_ms=45, max_body_chunk_gap_ms=8,
                        reasoning_bytes=100, reasoning="PRIVATE_REASONING", content="data:image/png;base64,PRIVATE")
        row = analyze_trace(self.trace([e("host-start", 0), e("request-start", 10, request_id="r"),
            e("request-fetch-start", 20, request_id="r"),
            e("response-complete", 50, request_id="r", stop_reason="stop", response_progress=progress),
            e("settled", 60, event_output=dict(events=4, bytes=100, reasoning="PRIVATE_REASONING"))]))
        self.assertEqual(row["timing_ms"]["first_reasoning"]["p50"], 5)
        self.assertEqual(row["timing_ms"]["first_content"]["p50"], 20)
        self.assertEqual(row["timing_ms"]["max_body_gap"]["p50"], 8)
        self.assertEqual(row["requests"][0]["progress"]["reasoning_bytes"], 100)
        self.assertNotIn("PRIVATE", json.dumps(row))
        self.assertEqual(row["unknown_usage_requests"], 1)
        self.assertEqual(row["usage"]["cacheRead"]["n"], 0)

    def test_campaign_discovery_is_explicit_and_never_reads_neighboring_campaigns(self):
        actor = self.root / "actors/001"
        actor.mkdir(parents=True)
        selected = actor / "host.jsonl"
        selected.write_text(json.dumps(self.event("host-start", 0)) + "\n")
        other = self.root / "other-campaign"
        other.mkdir()
        (other / "host.jsonl").write_text("unrelated")
        self.assertEqual(discover([self.root]), [selected.resolve()])

    def test_missing_fetch_does_not_invent_ttft_origin(self):
        e = self.event
        row = analyze_trace(self.trace([e("host-start", 0), e("request-start", 10, request_id="r"),
            e("response-first-chunk", 30, request_id="r"),
            e("response-complete", 50, request_id="r", stop_reason="stop", response_progress=dict(first_content_delta_ms=40)),
            e("settled", 60)]))
        self.assertEqual(row["timing_ms"]["first_body"]["n"], 0)
        self.assertEqual(row["timing_ms"]["first_content"]["n"], 0)
        self.assertEqual(row["completed_response_ms"]["p50"], 40)

    def test_current_campaign_disposition_is_not_goal_success(self):
        actor = self.root / "actors/001"
        actor.mkdir(parents=True)
        path = actor / "host.jsonl"
        path.write_text(json.dumps(self.event("host-start", 0)) + "\n")
        (self.root / "manifest.json").write_text(json.dumps(dict(schema="campaign-run/6", source_commit="abc")))
        receipt = dict(schema="campaign-receipt/4", outcome="player_task_complete_unassessed",
            normal_save_claimed_by_harness=False, driver=dict(schema="player-driver/4", attempts_charged=1,
                reported_usd="0.004", unpriced_requests=0, unpriced_request_usd="0.25", spent_usd="0.004", spend_complete=True))
        (self.root / "receipt.json").write_text(json.dumps(receipt))
        row = analyze_trace(path)["campaign_evidence"]
        self.assertEqual(row["receipt.json"]["outcome"], "player_task_complete_unassessed")
        self.assertFalse(row["receipt.json"]["normal_save_claimed_by_harness"])
        self.assertEqual(row["receipt.json"]["driver"]["attempts_charged"], 1)
        self.assertEqual((row["receipt.json"]["driver"]["spent_usd"], row["receipt.json"]["driver"]["spend_complete"]), ("0.004", True))
        # The driver record the dollar limit replaced is refused beside a current receipt, as any other version is.
        for old in ("player-driver/3", "player-driver/1"):
            receipt["driver"]["schema"] = old
            (self.root / "receipt.json").write_text(json.dumps(receipt))
            row = analyze_trace(path)["campaign_evidence"]
            self.assertEqual(row["metadata_coverage"]["receipt.json"], "unsupported_driver_version")
            self.assertNotIn("driver", row["receipt.json"])

    def test_an_archived_session_is_summarised_in_the_versions_the_index_lists(self):
        """A telemetry-3 trace and its /5 manifest and /3 receipt are read inside the run directory of a session the
        closed archive index lists, and nowhere else."""
        session = "a" * 32
        index = self.root / "archive-sessions.json"
        index.write_text(json.dumps(dict(schema="archive-sessions/1", sessions={session: dict(study="sealed", run="old01",
            versions=dict(manifest="campaign-run/5", receipt="campaign-receipt/3", driver="player-driver/3",
                host="player-host/3", host_telemetry=3, run_ending="campaign-watch-terminal/4"))})))
        run = self.root / "old01"
        actor = run / "actors/001"
        actor.mkdir(parents=True)
        path = actor / "host.jsonl"
        old = dict(schema="player-host/3", telemetry_version=3)
        path.write_text(json.dumps(self.event("host-start", 0, session=session, **old)) + "\n")
        (run / "manifest.json").write_text(json.dumps(dict(schema="campaign-run/5", session=session, source_commit="abc")))
        (run / "receipt.json").write_text(json.dumps(dict(schema="campaign-receipt/3", outcome="incomplete",
            driver=dict(schema="player-driver/3", attempts_charged=2, configured_estimate_usd=0.5))))
        with mock.patch("harness.evaluation.core.sources.ARCHIVE_INDEX", index):
            row = analyze_trace(path)
            self.assertEqual((row["coverage"], row["configuration"]["schema"]), ("player_host", "player-host/3"))
            evidence = row["campaign_evidence"]
            self.assertEqual(evidence["metadata_coverage"], {"manifest.json": "recorded", "receipt.json": "recorded"})
            self.assertEqual(evidence["receipt.json"]["driver"], dict(schema="player-driver/3", outcome=None, attempts_charged=2,
                host_seconds_used=None, configured_estimate_usd=0.5, missing_usage_attempts=None))
            # The same trace outside its run directory, or naming another session, is an unsupported version.
            loose = self.trace([self.event("host-start", 0, session=session, **old)])
            self.assertEqual(analyze_trace(loose)["coverage"], "unsupported_version")
            path.write_text(json.dumps(self.event("host-start", 0, session="b" * 32, **old)) + "\n")
            self.assertEqual(analyze_trace(path)["coverage"], "unsupported_version")

    def request_events(self, request_id, start, end, prompt, cost=None, tools=(), stop="toolUse"):
        """A request whose usage splits `prompt` across input and cache read (`None`: no cache write recorded); `tools` are tool-result times."""
        e = self.event
        usage = dict(input=1, cacheRead=2) if prompt is None else dict(input=1, cacheRead=prompt - 1, cacheWrite=0, output=5, reasoning=0)
        if cost is not None:
            usage["cost"] = dict(total=cost)
        events = [e("request-start", start, request_id=request_id),
            e("response-complete", end, request_id=request_id, stop_reason=stop, usage_available=True, usage=usage)]
        events += [e("tool-start", end + 1, request_id=request_id, tool_call_id=f"{request_id}-{index}") for index in range(len(tools))]
        events += [e("tool-result", at, request_id=request_id, tool_call_id=f"{request_id}-{index}") for index, at in enumerate(tools)]
        return events

    def test_response_time_is_banded_by_prompt_size_with_the_boundaries_pinned(self):
        r = self.request_events
        events = [self.event("host-start", 0),
            *r("r1", 0, 1000, 19_999, cost=.002, tools=[1500]),
            *r("r2", 2000, 4500, 20_000, cost=.004, tools=[5000, 5200]),  # two tool results: the first one counts
            *r("r3", 6000, 11_000, 150_000, cost=.010, stop="stop"),  # exactly 5 s is within 5 s
            *r("r4", 12_000, 12_500, None, stop="stop"),  # no known prompt size: in the whole, in no band
            *r("r5", 13_000, 20_000, 70_000, stop="error"),  # censored: not a sample
            *r("r6", 21_000, 22_000, 60_000, tools=[23_000]),  # no reported cost
            self.event("settled", 30_000)]
        by_prompt = analyze_trace(self.trace(events))["response_by_prompt"]
        self.assertEqual(by_prompt["response_ms"]["n"], 5)
        self.assertEqual((by_prompt["response_ms"]["p50"], by_prompt["response_ms"]["p95"]), (1000, 5000))
        self.assertEqual((by_prompt["within_2s"], by_prompt["within_5s"]), (.6, 1.0))
        self.assertEqual(by_prompt["unknown_prompt_responses"], 1)
        bands = {band["band"]: band for band in by_prompt["bands"]}
        self.assertEqual(list(bands), ["under 20,000", "20,000 to 60,000", "60,000 to 100,000", "100,000 to 150,000", "over 150,000"])
        self.assertEqual([band["response_ms"]["n"] for band in bands.values()], [1, 1, 1, 0, 1])
        self.assertEqual(bands["under 20,000"]["response_ms"]["p50"], 1000)
        self.assertEqual((bands["20,000 to 60,000"]["within_2s"], bands["20,000 to 60,000"]["within_5s"]), (0.0, 1.0))
        self.assertEqual(bands["under 20,000"]["mean_cost_usd"], .002)
        self.assertEqual((bands["60,000 to 100,000"]["mean_cost_usd"], bands["60,000 to 100,000"]["cost_n"]), (None, 0))
        self.assertEqual((bands["100,000 to 150,000"]["response_ms"]["p50"], bands["100,000 to 150,000"]["within_5s"]), (None, None))
        self.assertEqual((bands["over 150,000"]["within_5s"], bands["over 150,000"]["mean_cost_usd"]), (1.0, .01))
        # First tool result to the previous request's first tool result; a request without one neither ends nor starts an interval.
        wait = by_prompt["first_tool_result_interval_ms"]
        self.assertEqual((wait["n"], wait["p50"], wait["p95"]), (2, 3500, 18_000))
        self.assertEqual((wait["within_2s"], wait["within_5s"]), (0.0, .5))

    def test_runs_and_the_selection_pool_responses_instead_of_averaging_trace_percentiles(self):
        def write(run, actor, durations):
            directory = self.root / run / "actors" / actor
            directory.mkdir(parents=True)
            events, at = [self.event("host-start", 0)], 0
            for index, duration in enumerate(durations):
                events += self.request_events(f"r{index}", at, at + duration, 10_000)
                at += duration + 100
            (directory / "host.jsonl").write_text("".join(json.dumps(x) + "\n" for x in [*events, self.event("settled", at)]))
        write("runA", "001", [1000, 3000, 9000])
        write("runA", "002", [2000])
        write("runB", "001", [4000, 6000])
        report = host_summary([self.root / "runA", self.root / "runB"])
        self.assertEqual([(run["run"].rsplit("/", 1)[-1], run["traces"], run["response_by_prompt"]["response_ms"]["n"],
            run["response_by_prompt"]["response_ms"]["p50"]) for run in report["runs"]], [("runA", 2, 4, 2000), ("runB", 1, 2, 4000)])
        selection = report["selection"]["response_by_prompt"]
        self.assertEqual((report["selection"]["traces"], selection["response_ms"]["n"], selection["response_ms"]["p50"],
            selection["response_ms"]["p95"]), (3, 6, 3000, 9000))
        self.assertEqual((selection["within_2s"], selection["within_5s"]), (2 / 6, 4 / 6))
        self.assertEqual(selection["bands"][0]["response_ms"]["n"], 6)
        # A trace's own figures are those of its own responses (nearest rank 2 of 3 is 3000, not a mean).
        first = next(r for r in report["traces"] if r["path"].endswith("runA/actors/001/host.jsonl"))
        self.assertEqual(first["response_by_prompt"]["response_ms"]["p50"], 3000)
        text = markdown(report)
        self.assertIn("## Response time by prompt size, 3 selected traces", text)
        self.assertIn("| All responses | 6 | 3.0 | 9.0 | 33.3% | 66.7% | unknown |", text)
        self.assertIn("| Under 20,000 | 6 | 3.0 | 9.0 | 33.3% | 66.7% | unknown |", text)
        self.assertIn("| runA | 2 | 4 | 2.0 | 9.0 | 50.0% | 75.0% | unknown |", text)
