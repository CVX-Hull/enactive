"""Synthetic accounting fixtures; these tests make no native efficacy claims."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from harness.gameplay.contracts import ContractError
from harness.gameplay.evaluation import MAX_JSON_BYTES, RunRecorder, summarize_runs, validate_run


def manifest(**changes):
    value = {
        "run_id": "fixture-1", "scenario_id": "route-a", "family_id": "clear-route",
        "split": "development", "lane": "synthetic", "condition": "primitive",
        "source_commit": "a" * 40, "native_build": None,
        "native_build_missing_reason": "Synthetic fixture", "model_id": "fixture-model",
        "model_id_missing_reason": None, "configuration_id": "fixture-config",
        "configuration_id_missing_reason": None, "protocol_version": "native-v3",
        "budgets": {"primitives": 8, "turns": 32, "wall_ms": 120000,
                    "model_calls": 10, "model_call_ms": 30000, "input_tokens": 10000,
                    "input_tokens_missing_reason": None, "output_tokens": 10000,
                    "output_tokens_missing_reason": None, "cost_usd": 1.0,
                    "cost_usd_missing_reason": None},
        "start_description": "Constructed accounting fixture", "evidence": [],
        "admission": {"monotonic_ms": 100000, "session": "world-1", "game_turn": 10,
                      "game_turn_missing_reason": None},
    }
    value.update(changes)
    return value


def evidence():
    return {"schema": "gameplay/1", "record_type": "EvidenceRef",
            "observation_id": "observation-1", "session": "world-1", "revision": 1,
            "timestamp_ms": 1000, "received_monotonic": 100, "turn": 10,
            "frame_path": "retained/frame.png", "frame_sha256": "a" * 64,
            "boundary_kind": "normal_play", "visibility_version": "cdda-visible/1"}


def action(number=1, elapsed=20, **changes):
    payload = {"action_id": f"primitive-{number}", "transport_disposition": "returned",
               "dispatch_state": "dispatched", "duration_ms": 10,
               "verified_steps": 1, "verified_steps_missing_reason": None,
               "invalid": False, "stale": False, "unknown": False,
               "verified_no_progress": False}
    payload.update(changes)
    return event(f"action-{number}", elapsed, "action", payload)


def event(identity, elapsed, kind, payload):
    return {"event_id": identity, "elapsed_ms": elapsed, "kind": kind,
            "session": "world-1", "game_turn": 11, "game_turn_missing_reason": None,
            "evidence": [], "payload": payload}


def model(number=1, elapsed=10, **changes):
    payload = {"role": "planner", "model_id": "model-a", "configuration_id": "config-a",
               "duration_ms": 5, "status": "completed", "input_tokens": 100,
               "input_tokens_missing_reason": None, "output_tokens": 20,
               "output_tokens_missing_reason": None, "cached_input_tokens": 40,
               "cached_input_tokens_missing_reason": None, "cost_usd": 0.02,
               "cost_usd_missing_reason": None}
    payload.update(changes)
    return event(f"model-{number}", elapsed, "model_call", payload)


def outcome(**changes):
    value = {"disposition": "success", "elapsed_ms": 100, "session": "world-1",
             "game_turn": 12, "game_turn_missing_reason": None,
             "verified_steps": 1, "verified_steps_missing_reason": None,
             "first_useful_action_event_id": "action-1",
             "first_useful_action_missing_reason": None, "harmful_actions": None,
             "harmful_actions_missing_reason": "Not assessed", "deaths": 0,
             "deaths_missing_reason": None, "evidence": [],
             "assessment": {"assessor": "fixture-author", "method": "Constructed fixture"}}
    value.update(changes)
    return value


def run(events=None, final=None, **manifest_changes):
    recorder = RunRecorder(manifest(**manifest_changes))
    for item in events if events is not None else [action()]:
        recorder.record(item)
    recorder.finish(final or outcome())
    return recorder.to_dict()


class EvaluationTests(unittest.TestCase):
    def test_attempts_dispatch_and_progress_are_independent(self):
        events = [action(1, 20), action(2, 30, transport_disposition="rejected",
                  dispatch_state="not_dispatched", verified_steps=0, invalid=True,
                  verified_no_progress=True), action(3, 40, transport_disposition="unknown",
                  dispatch_state="unknown", verified_steps=None,
                  verified_steps_missing_reason="No reconciliation", unknown=True)]
        result = summarize_runs([run(events, outcome(disposition="partial"))])["groups"][0]
        self.assertEqual(result["primitive_attempts"], 3)
        self.assertEqual(result["known_dispatches"], 1)
        self.assertEqual(result["unknown_dispatches"], 1)
        self.assertEqual(result["action_flags"], {"invalid": 1, "stale": 0, "unknown": 1,
                                                 "verified_no_progress": 1})
        self.assertEqual(result["action_verified_steps"], {"known_subtotal": 1,
                         "known_count": 2, "missing_count": 1})
        self.assertEqual(result["verified_steps"]["known_subtotal"], 1)
        self.assertEqual(result["outcomes"]["partial"], 1)

    def test_failed_calls_cost_cache_roles_switches_and_percentiles(self):
        events = [model(), model(2, 20, role="monitor", model_id="model-b", duration_ms=15,
                   status="timed_out", cost_usd=None, cost_usd_missing_reason="Provider absent"),
                  model(3, 40, model_id="model-b", duration_ms=30, status="failed"), action(elapsed=50)]
        group = summarize_runs([run(events)])["groups"][0]
        calls = group["model_calls"]
        self.assertEqual(calls["input_tokens"]["known_subtotal"], 300)
        self.assertEqual(calls["cached_input_tokens"]["known_subtotal"], 120)
        self.assertEqual(calls["cost_usd"], {"known_subtotal": 0.04, "known_count": 2,
                                           "missing_count": 1})
        self.assertEqual(calls["duration_ms"], {"count": 3, "median": 15, "p95": 30})
        self.assertEqual(group["model_switches"], 1)
        self.assertEqual(calls["by_role"]["monitor"]["statuses"]["timed_out"], 1)
        self.assertEqual(group["time_to_first_useful_action_ms"]["known_subtotal"], 50)

    def test_final_wait_and_censored_world_reload_are_retained(self):
        first = run(final=outcome(elapsed_ms=1000))
        second = run([action(1, 20, verified_steps=None,
                     verified_steps_missing_reason="Reload", transport_disposition="unknown",
                     dispatch_state="unknown", unknown=True)],
                     outcome(disposition="unknown", elapsed_ms=2000, session="world-2",
                             game_turn=100, first_useful_action_event_id=None,
                             first_useful_action_missing_reason="No verified useful input",
                             verified_steps=None, verified_steps_missing_reason="Reload"),
                     run_id="fixture-2")
        group = summarize_runs([first, second])["groups"][0]
        self.assertEqual(group["runs"], 2)
        self.assertEqual(group["censored_runs"], 1)
        self.assertEqual(group["wall_ms"]["known_subtotal"], 3000)
        self.assertEqual(group["game_turns"], {"known_subtotal": 2,
                         "known_count": 1, "missing_count": 1})
        self.assertEqual(group["verified_steps"]["missing_count"], 1)
        self.assertEqual(group["harmful_actions"]["known_subtotal"], None)

    def test_declared_comparison_identities_split_groups(self):
        base = run([model(), action()])
        variants = []
        for key, value in {"family_id": "blocked", "split": "held_out", "lane": "native",
                           "condition": "bounded_skill", "source_commit": "b" * 40,
                           "model_id": "other-model", "configuration_id": "other-config",
                           "native_build": "other-native"}.items():
            child = deepcopy(base)
            child["manifest"][key] = value
            if key == "native_build":
                child["manifest"]["native_build_missing_reason"] = None
            if key == "lane":
                child["manifest"]["evidence"] = [evidence()]
                child["outcome"]["evidence"] = [{**evidence(), "turn": 12}]
                child["manifest"]["native_build"] = "native-receipt"
                child["manifest"]["native_build_missing_reason"] = None
            child["manifest"]["run_id"] = key
            variants.append(child)
        child = deepcopy(base)
        child["events"][0]["payload"]["configuration_id"] = "other-call-config"
        child["manifest"]["run_id"] = "call-config"
        variants.append(child)
        self.assertEqual(len(summarize_runs([base, *variants])["groups"]), 9)
        with self.assertRaises(ContractError):
            summarize_runs([base, base])

    def test_sessions_and_censored_call_paths_do_not_fragment_repetitions(self):
        first = run([model(), action()])
        second = run([], outcome(disposition="unknown", verified_steps=None,
            verified_steps_missing_reason="No action", first_useful_action_event_id=None,
            first_useful_action_missing_reason="No action", session="world-2", game_turn=0),
            run_id="second", admission={"monotonic_ms": 300000, "session": "world-2",
                                      "game_turn": -1, "game_turn_missing_reason": None})
        groups = summarize_runs([first, second])["groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["runs"], 2)
        self.assertEqual(groups[0]["censored_runs"], 1)
        self.assertEqual(groups[0]["game_turns"]["known_subtotal"], 3)
        self.assertEqual(groups[0]["model_calls"]["by_identity"][0]["count"], 1)

    def test_first_useful_action_requires_known_dispatch(self):
        for dispatch in ("not_dispatched", "unknown"):
            with self.subTest(dispatch=dispatch), self.assertRaisesRegex(ContractError, "known dispatched"):
                run([action(transport_disposition=dispatch, dispatch_state=dispatch,
                            verified_steps=0, unknown=dispatch == "unknown")])
        # Zero displacement does not exclude a useful menu input.
        run([action(verified_steps=0)])

    def test_native_provenance_and_unknown_failure_remain_distinct(self):
        child = run()
        child["manifest"].update(lane="native", native_build="receipt",
                                 native_build_missing_reason=None)
        with self.assertRaisesRegex(ContractError, "start evidence"):
            validate_run(child)
        child["manifest"]["evidence"] = [evidence()]
        with self.assertRaisesRegex(ContractError, "final evidence"):
            validate_run(child)
        child["outcome"]["disposition"] = "unknown"
        child["outcome"]["assessment"]["method"] = "No final frame after native timeout"
        self.assertEqual(validate_run(child)["outcome"]["disposition"], "unknown")
        child["outcome"].update(disposition="success", evidence=[{**evidence(), "turn": 12}])
        validate_run(child)
        child["manifest"]["evidence"][0]["session"] = "other-world"
        with self.assertRaisesRegex(ContractError, "start evidence"):
            validate_run(child)
        child["manifest"]["evidence"][0]["session"] = "world-1"
        child["outcome"]["evidence"][0]["turn"] = 10
        with self.assertRaisesRegex(ContractError, "final evidence"):
            validate_run(child)

    def test_missing_turn_cannot_hide_same_session_regression(self):
        child = run([model(), action()])
        child["events"][0]["game_turn"] = 20
        child["events"][1].update(game_turn=None, game_turn_missing_reason="Unavailable")
        with self.assertRaisesRegex(ContractError, "turns cannot decrease"):
            validate_run(child)
        child["outcome"]["game_turn"] = 21
        validate_run(child)

    def test_empty_model_usage_is_unknown_not_free(self):
        calls = summarize_runs([run()])["groups"][0]["model_calls"]
        self.assertEqual(calls["count"], 0)
        self.assertIsNone(calls["cost_usd"]["known_subtotal"])
        self.assertEqual(calls["cost_usd"]["known_count"], 0)

    def test_recording_snapshots_exclusive_write_and_final_state(self):
        source = manifest()
        recorder = RunRecorder(source)
        source["admission"]["session"] = "tampered"
        item = action()
        recorder.record(item)
        item["payload"]["verified_steps"] = 0
        final = outcome()
        recorder.finish(final)
        final["elapsed_ms"] = 5
        snapshot = recorder.to_dict()
        snapshot["events"].clear()
        self.assertEqual(len(recorder.to_dict()["events"]), 1)
        self.assertEqual(recorder.to_dict()["manifest"]["admission"]["session"], "world-1")
        self.assertEqual(recorder.to_dict()["outcome"]["elapsed_ms"], 100)
        for operation in (lambda: recorder.record(action(2)), lambda: recorder.finish(outcome())):
            with self.assertRaises(ContractError):
                operation()
        with tempfile.TemporaryDirectory(prefix="cdda-evaluation-") as directory:
            path = Path(directory) / "run.json"
            recorder.write(path)
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                recorder.write(path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(validate_run(original), recorder.to_dict())

    def test_unfinished_or_invalid_events_never_disappear(self):
        recorder = RunRecorder(manifest())
        with self.assertRaises(ContractError):
            recorder.to_dict()
        recorder.record(action())
        with self.assertRaises(ContractError):
            recorder.record(action())
        recorder.finish(outcome())
        self.assertEqual(len(recorder.to_dict()["events"]), 1)

    def test_rejects_exact_schema_types_identity_time_and_missingness_flaws(self):
        base = run([model(), action()])
        def changed(path, value):
            child = deepcopy(base)
            target = child
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            return child
        mutations = [(["schema"], "evaluation/0"), (["unexpected"], True),
            (["manifest", "source_commit"], "a" * 40 + "\n"),
            (["manifest", "admission", "game_turn"], True),
            (["manifest", "admission", "game_turn"], 10.0),
            (["events", 1, "elapsed_ms"], 5),
            (["events", 0, "payload", "duration_ms"], 11),
            (["events", 1, "payload", "verified_steps"], 2),
            (["events", 1, "payload", "extra"], "ignored?"),
            (["events", 0, "payload", "cached_input_tokens"], 101),
            (["events", 0, "payload", "cost_usd"], None),
            (["events", 0, "payload", "input_tokens"], -1),
            (["events", 0, "payload", "output_tokens"], False),
            (["events", 1, "payload", "verified_no_progress"], True),
            (["events", 1, "event_id"], "model-1"),
            (["outcome", "elapsed_ms"], 19),
            (["outcome", "game_turn"], 9),
            (["outcome", "first_useful_action_event_id"], "model-1"),
            (["outcome", "verified_steps"], None),
            (["outcome", "harmful_actions_missing_reason"], None),
            (["outcome", "assessment", "method"], ""),
            (["manifest", "start_description"], "x" * 4097)]
        for path, value in mutations:
            with self.subTest(path=path, value=str(value)[:20]), self.assertRaises(ContractError):
                validate_run(changed(path, value))
        duplicate = deepcopy(base)
        duplicate["events"].append(deepcopy(duplicate["events"][-1]))
        duplicate["events"][-1]["event_id"] = "distinct-event-same-action"
        with self.assertRaises(ContractError):
            validate_run(duplicate)
        for data in ('{"schema":"evaluation/1","schema":"evaluation/1"}', b"x" * (MAX_JSON_BYTES + 1)):
            with self.assertRaises(ContractError):
                validate_run(data)
        for number in (float("nan"), float("inf"), -1, 10**1000):
            with self.assertRaises(ContractError):
                validate_run(changed(["outcome", "elapsed_ms"], number))
        oversized = deepcopy(base)
        oversized["events"] *= 2049
        with self.assertRaises(ContractError):
            validate_run(oversized)

    def test_model_configuration_change_does_not_count_as_model_switch(self):
        child = run([model(), model(2, 15, configuration_id="other"), action()])
        self.assertEqual(summarize_runs([child])["groups"][0]["model_switches"], 0)

    def test_failed_finish_preserves_recorder_and_type_coercions_are_rejected(self):
        recorder = RunRecorder(manifest())
        recorder.record(action())
        with self.assertRaises(ContractError):
            recorder.finish(outcome(elapsed_ms=19))
        recorder.record(action(2, 25))
        recorder.finish(outcome(verified_steps=2))
        self.assertEqual(len(recorder.to_dict()["events"]), 2)
        child = recorder.to_dict()
        child["events"] = tuple(child["events"])
        with self.assertRaises(ContractError):
            validate_run(child)

    def test_observation_recovery_intervention_and_public_decisions(self):
        events = [event("o", 5, "observation", {"duration_ms": 5, "available": False, "fresh": False}),
                  event("i", 6, "intervention", {"actor": "operator", "operation": "pause",
                        "outcome": "paused", "reason": "Visible operator request"}),
                  event("r", 7, "recovery", {"actor": "autonomous", "operation": "inspect",
                        "outcome": "unknown", "reason": "No fresh observation"}),
                  event("d", 8, "decision", {"decision": "stop", "reason": "Inspection unavailable",
                        "actor": "operator", "model_id": None,
                        "model_id_missing_reason": "Manual decision", "expected": [],
                        "observed": [], "unknowns": ["Outcome unavailable"]})]
        final = outcome(disposition="budget_exhausted", verified_steps=0,
                        first_useful_action_event_id=None,
                        first_useful_action_missing_reason="No useful action")
        group = summarize_runs([run(events, final)])["groups"][0]
        self.assertEqual(group["interventions"], {"operator": 1, "autonomous": 0})
        self.assertEqual(group["recoveries"], {"operator": 0, "autonomous": 1})
        self.assertEqual(group["observations"], {"count": 1, "unavailable": 1, "stale": 0})
        self.assertEqual(group["censored_runs"], 1)

    def test_cli_validates_summarizes_and_rejects_any_bad_input(self):
        with tempfile.TemporaryDirectory(prefix="cdda-evaluation-cli-") as directory:
            path = Path(directory) / "valid.json"
            path.write_text(json.dumps(run()))
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            def invoke(*arguments):
                return subprocess.run([sys.executable, "-m", "tools.evaluate", *map(str, arguments)],
                                      capture_output=True, text=True, env=env, check=False)
            result = invoke("validate", path)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = invoke("summary", path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["groups"][0]["runs"], 1)
            bad = Path(directory) / "bad.json"
            bad.write_text("{}")
            result = invoke("summary", path, bad)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertIn("bad.json", result.stderr)
            self.assertNotEqual(invoke("validate", Path(directory) / "missing").returncode, 0)
            self.assertNotEqual(invoke("summary", path, path).returncode, 0)
            self.assertNotEqual(invoke("validate").returncode, 0)
            bad.write_bytes(b" " * (MAX_JSON_BYTES + 1))
            self.assertNotEqual(invoke("validate", bad).returncode, 0)
