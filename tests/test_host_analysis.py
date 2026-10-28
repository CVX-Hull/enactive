"""Deterministic diagnostic fixtures; no provider, native or quality qualification."""
import json
from pathlib import Path
import tempfile
import unittest

from harness.gameplay.contracts import ContractError
from tools.host_analysis import analyze_trace, discover, host_summary
from tools.observer_analysis import identity, witness_summary


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

    def test_directory_patterns_read_adviser_once_but_explicit_duplicates_refuse(self):
        path = self.trace([self.event("host-start", 0)], "driver-adviser-active.jsonl")
        self.assertEqual(discover([self.root]), [path.resolve()])
        with self.assertRaises(ContractError):
            discover([self.root, path])

    def test_clock_regression_censors_all_durations(self):
        e = self.event
        row = analyze_trace(self.trace([e("host-start", 0), e("request-start", 10, request_id="r"),
            e("response-complete", 9, request_id="r", stop_reason="stop"), e("settled", 20)]))
        self.assertFalse(row["clock_valid"])
        self.assertIsNone(row["request_share"])
        self.assertIsNone(row["host_ms"])
        self.assertEqual(row["completed_response_ms"]["n"], 0)
        huge = analyze_trace(self.trace([e("host-start", 10 ** 400)]))
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
        with self.assertRaises(ContractError):
            discover([empty, empty])

    def test_early_abort_is_retained_and_future_telemetry_is_not_interpreted(self):
        e = self.event
        row = analyze_trace(self.trace([e("abort", 0, reason="cancelled"), e("settled", 1, reason="cancelled", ok=False)]))
        self.assertEqual(row["coverage"], "runner_only")
        self.assertEqual(row["terminal"]["reason"], "cancelled")
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

    def test_exact_witness_join_deduplicates_exports_and_keeps_misses(self):
        state = dict(protocol=7, session="s", revision=2, frame="f", timestamp_ms=100, frame_ok=True,
            boundary=dict(kind="normal_play", id="b", control_generation=1, recovery_operations=[]),
            takeover_generation=0, pause_origin="host", frame_geometry={"output_width": 10})
        evidence = self.root / "evidence.json"
        evidence.write_text(json.dumps(dict(store_version=6, entries=[dict(reference=dict(observation_id="source", session="s", revision=2, timestamp_ms=100), observation=state),
            dict(reference=dict(observation_id="missing", session="other", revision=2, timestamp_ms=100), observation={**state, "session": "other"})])))
        frame = dict(frame_identity=json.dumps(identity(state)), native_capture_epoch_ms=100,
            dom_replaced_epoch_ms=120, outcome="dom_replaced")
        observer = self.root / "observer.json"
        observer.write_text(json.dumps(dict(schema="observer-timing/3", dropped=dict(frames=3), frames=[frame, frame])))
        report = witness_summary([evidence, observer, observer])
        self.assertEqual(report["unique_frame_capture_to_dom_ms"]["n"], 1)
        self.assertEqual(report["unique_frame_capture_to_dom_ms"]["sum"], 20)
        self.assertEqual(report["missing_source_matches"], 1)
        self.assertEqual(report["exports"][0]["dropped"]["frames"], 3)
        self.assertIn("not physical paint", report["scope"])
        negative = {**frame, "dom_replaced_epoch_ms": 90}
        observer.write_text(json.dumps(dict(schema="observer-timing/3", frames=[negative, frame])))
        invalid = witness_summary([evidence, observer])
        self.assertEqual(invalid["source_rows"][0]["capture_to_dom_ms"], -10)
        self.assertEqual(invalid["source_rows"][0]["missing_reason"], "invalid_cross_clock_interval")
        self.assertEqual(invalid["unique_frame_capture_to_dom_ms"]["n"], 0)
        # Same basename/revision without matching geometry never acquires a witness.
        frame["frame_identity"] = json.dumps(identity({**state, "frame_geometry": {"output_width": 20}}))
        observer.write_text(json.dumps(dict(schema="observer-timing/3", frames=[frame])))
        self.assertEqual(witness_summary([evidence, observer])["missing_source_matches"], 2)
        observer.write_text(json.dumps(dict(schema="observer-timing/3", frames=[42])))
        with self.assertRaises(ContractError):
            witness_summary([evidence, observer])
