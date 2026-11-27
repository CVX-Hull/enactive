"""The delegate call starts the one delegate the lead names and reports what happened, with stand-in commands.

No coding agent is started here. Each stand-in is a small script that records that it ran and then behaves as
one of the cases the lead has to be told about: a hand-back, a start that fails, an empty reply, a refusal, a
sandbox that cannot run the acceptance check. The tracked definitions are read only to see that each coding
agent offers every role and that every placeholder they use is one the call fills.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import pytest

from tools import delegate

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"worker", "reviewer", "explorer", "locator"}
BRIEF = "Role: worker, named for the test\nGoal: write note.txt\n"


def script(path: Path, body: str) -> str:
    path.write_text(f"import json, os, pathlib, sys\n{body}\n", encoding="utf-8")
    return str(path)


@pytest.fixture
def stand_ins(tmp_path):
    """Three stand-in coding agents; each appends its name to `started` when it runs."""
    started = tmp_path / "started"
    mark = f"open({str(started)!r}, 'a').write(NAME + '\\n')\n"
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    subprocess.run(["git", "init", "-q", str(worktree)], check=True)
    subprocess.run(["git", "-C", str(worktree), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit",
                    "-q", "--allow-empty", "-m", "base"], check=True)
    first_turn = {"type": "turn.completed", "usage": {"input_tokens": 10, "cached_input_tokens": 3, "output_tokens": 5}}
    turns = "\n".join(json.dumps(record) for record in (
        first_turn,
        {"type": "item.completed", "usage": {"input_tokens": 1000}},
        {"type": "turn.completed", "usage": {"input_tokens": 8, "cached_input_tokens": 2, "cache_write_input_tokens": 0,
                                             "output_tokens": 4, "reasoning_output_tokens": 2}},
    ))
    bodies = {
        # Writes its reply to the file it is told, like a coding agent with a last-message option, and edits the tree.
        "first": "NAME = 'first'\n" + mark + "brief = sys.stdin.read()\npathlib.Path('note.txt').write_text('written')\n"
                 "pathlib.Path(sys.argv[1]).write_text('model ' + sys.argv[2] + ' effort ' + sys.argv[3] + ' key ' "
                 "+ os.environ.get('SECRET_KEY', 'absent') + '\\n' + brief + '\\nAcceptance check: not run\\n')\n"
                 f"print({turns!r})",
        # Prints one object with its reply, usage and served models, and takes the brief as an argument.
        "second": "NAME = 'second'\n" + mark + "print(json.dumps({'result': 'reviewed: ' + sys.argv[1][:40], "
                  "'usage': {'input_tokens': 20, 'cache_read_input_tokens': 11, 'cache_creation_input_tokens': 4, "
                  "'output_tokens': 7}, 'modelUsage': {'served-z': {}, 'served-a': {}}}))",
        "third": "NAME = 'third'\n" + mark + "print(json.dumps({'status': 'SUCCESS', 'response': 'explored', "
                 "'usage': {'input_tokens': 15, 'cache_read_tokens': 5, 'output_tokens': 4, 'thinking_tokens': 3}}))",
        "silent": "NAME = 'silent'\n" + mark + "print('a tool was denied', file=sys.stderr)\n"
                  "if len(sys.argv) > 1: print(sys.argv[1])",
        "refusing": "NAME = 'refusing'\n" + mark + "print('You have hit your usage limit', file=sys.stderr)\nsys.exit(1)",
        "crashing": "NAME = 'crashing'\n" + mark + "print(json.dumps({'usage': {'output_tokens': 2}}))\n"
                    "print('boom', file=sys.stderr)\nsys.exit(3)",
        # Fails with an output record whose timing happens to be 429, and says nothing of a refusal.
        "timed": "NAME = 'timed'\n" + mark + "print(json.dumps({'result': '', 'first_token_ms': 429}))\n"
                 "print('stopped', file=sys.stderr)\nsys.exit(1)",
        # Fails with an output record that says in words that it was refused.
        "declining": "NAME = 'declining'\n" + mark
                     + "print(json.dumps({'result': '', 'error': {'message': 'You have hit your usage limit'}}))\nsys.exit(1)",
        # Fails after a line-per-record turn whose token count happens to be 429.
        "counting": "NAME = 'counting'\n" + mark
                    + "print(json.dumps({'type': 'turn.completed', 'usage': {'output_tokens': 429}}))\n"
                    "print('stopped', file=sys.stderr)\nsys.exit(1)",
        # Never ends, and leaves a child that ignores the request to stop.
        "slow": "NAME = 'slow'\n" + mark + f"print({json.dumps(first_turn)!r}, flush=True)\n"
                "print('{\"type\":', flush=True)\n"
                "import subprocess, time\nchild = subprocess.Popen([sys.executable, '-c', "
                "'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)'])\n"
                f"pathlib.Path({str(tmp_path / 'child')!r}).write_text(str(child.pid))\ntime.sleep(60)",
    }
    commands = {name: script(tmp_path / name, body) for name, body in bodies.items()}
    version = [sys.executable, "-c", "print('9.9.9')"]

    jsonl_usage = {"read": "stdout_jsonl", "where": {"type": "turn.completed"}, "tokens": {
        "input_tokens": "usage.input_tokens", "cached_input_tokens": "usage.cached_input_tokens",
        "cache_write_input_tokens": "usage.cache_write_input_tokens", "output_tokens": "usage.output_tokens"}}
    json_usage = {"read": "stdout_json", "tokens": {
        "input_tokens": "usage.input_tokens", "cached_input_tokens": "usage.cache_read_input_tokens",
        "cache_write_input_tokens": "usage.cache_creation_input_tokens", "output_tokens": "usage.output_tokens"},
        "models": "modelUsage"}
    response_usage = {"read": "stdout_json", "tokens": {
        "input_tokens": "usage.input_tokens", "cached_input_tokens": "usage.cache_read_tokens",
        "output_tokens": "usage.output_tokens"}}

    def agent(name, argv, brief="stdin", reply=None, usage=json_usage):
        if reply is None:
            reply = {"stdout_json": "result"}
        return {"name": name, "version": version, "refusals": ["usage limit", "sign ?in", r"\b429\b"], "usage": usage,
                "roles": {name: {"argv": argv.copy(), "brief": brief, "reply": reply, "read_only": name != "worker"}
                          for name in ROLES}}

    definitions = {"schema": "delegates/4", "role_instruction": "You are the {role}.", "drop_environment": ["SECRET_KEY"],
                   "coding_agents": {
                       "first": agent("First", [sys.executable, commands["first"], "{reply_file}", "{model}", "{effort}"],
                                      reply="file", usage=jsonl_usage),
                       "second": agent("Second", [sys.executable, commands["second"], "{brief}"], brief="argument"),
                       "third": agent("Third", [sys.executable, commands["third"]],
                                      reply={"stdout_json": "response"}, usage=response_usage),
                       "silent": agent("Silent", [sys.executable, commands["silent"]]),
                       "refusing": agent("Refusing", [sys.executable, commands["refusing"]]),
                       "crashing": agent("Crashing", [sys.executable, commands["crashing"]]),
                       "timed": agent("Timed", [sys.executable, commands["timed"]]),
                       "declining": agent("Declining", [sys.executable, commands["declining"]]),
                       "counting": agent("Counting", [sys.executable, commands["counting"]], reply="file", usage=jsonl_usage),
                       "slow": agent("Slow", [sys.executable, commands["slow"]], reply="file", usage=jsonl_usage),
                       "absent": agent("Absent", [str(tmp_path / "no-such-command")]),
                       "partly": {"name": "Partly", "version": version, "refusals": [], "usage": json_usage,
                                  "roles": {"worker": {"unavailable": "no start that works, 1 January 2026"}}}}}

    def start(coding_agent, role="worker", **options):
        options = {"model": "model-one", "effort": "high", "brief": BRIEF, "check": None, "timeout": None} | options
        result = delegate.start(definitions, coding_agent=coding_agent, role=role, worktree=worktree,
                                out=tmp_path / "out", **options)
        ran = started.read_text().split() if started.exists() else []
        return result, ran

    start.worktree, start.out, start.definitions, start.child = worktree, tmp_path / "out", definitions, tmp_path / "child"
    return start


def test_the_named_delegate_is_started_with_its_model_effort_role_and_brief_and_no_other(stand_ins, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a provider key")
    result, ran = stand_ins("first", role="worker")
    assert ran == ["first"]
    assert (result["outcome"], result["coding_agent"], result["coding_agent_version"]) == ("handed_back", "First", "9.9.9")
    reply = Path(result["hand_back"]).read_text()
    # The lead's choice reaches the command, the role's instruction leads the brief, and a listed key does not pass.
    assert reply.startswith("model model-one effort high key absent\nYou are the worker.\n\nRole: worker")
    assert result["uncommitted"] == ["note.txt"] and result["commits"] == []

    result, ran = stand_ins("second", role="reviewer")
    assert ran == ["first", "second"] and result["outcome"] == "handed_back"
    assert Path(result["hand_back"]).read_text().startswith("reviewed: You are the reviewer.")


def test_a_json_reply_file_contains_only_the_reply_and_the_report_contains_usage_and_sorted_models(stand_ins):
    result, _ = stand_ins("second", role="reviewer")
    stdout = json.loads((stand_ins.out / "stdout.txt").read_text())
    reply = "reviewed: " + (stand_ins.out / "brief.txt").read_text()[:40]
    assert (stand_ins.out / "reply.md").read_text() == stdout["result"] == reply
    assert result["usage"] == {"input_tokens": 20, "cached_input_tokens": 11, "cache_write_input_tokens": 4,
                               "output_tokens": 7}
    assert result["models_reported"] == ["served-a", "served-z"]


def test_usage_is_summed_over_only_the_matching_json_lines(stand_ins):
    result, _ = stand_ins("first")
    assert result["usage"] == {"input_tokens": 18, "cached_input_tokens": 5, "cache_write_input_tokens": 0,
                               "output_tokens": 9}
    assert result["models_reported"] is None


def test_usage_is_reported_even_when_a_run_fails(stand_ins):
    result, _ = stand_ins("crashing")
    assert result["outcome"] == "failed"
    assert result["usage"] == {"input_tokens": None, "cached_input_tokens": None, "cache_write_input_tokens": None,
                               "output_tokens": 2}


@pytest.mark.parametrize("stdout", ["not JSON", "[]", "{}", '{"result": 42}'])
def test_stdout_without_a_usable_json_reply_gives_an_empty_reply_and_no_usage(stand_ins, stdout):
    stand_ins.definitions["coding_agents"]["silent"]["roles"]["worker"]["argv"].append(stdout)
    result, _ = stand_ins("silent")
    assert result["outcome"] == "empty_reply" and "the reply was not read" in result["detail"]
    assert (stand_ins.out / "reply.md").read_text() == ""
    assert (stand_ins.out / "stdout.txt").read_text() == stdout + "\n"
    assert result["usage"] is None and result["models_reported"] is None


@pytest.mark.parametrize(("coding_agent", "outcome", "detail", "ran"), [
    ("absent", "failed_start", "is not on the path", []),
    ("silent", "empty_reply", "a tool was denied", ["silent"]),
    ("refusing", "refused", "usage limit", ["refusing"]),
    ("crashing", "failed", "exit code 3: boom", ["crashing"]),
    ("timed", "failed", "exit code 1: stopped", ["timed"]),
    ("declining", "refused", "usage limit", ["declining"]),
    ("counting", "failed", "exit code 1: stopped", ["counting"]),
    ("partly", "unavailable", "no start that works", []),
])
def test_a_run_with_no_hand_back_is_reported_as_what_it_was_and_nothing_else_is_started(stand_ins, coding_agent, outcome, detail, ran):
    result, started = stand_ins(coding_agent)
    assert result["outcome"] == outcome and detail in result["detail"] and result["hand_back"] is None
    assert started == ran


def test_a_run_past_its_time_limit_is_reported_and_nothing_it_started_is_left_running(stand_ins):
    result, started = stand_ins("slow", timeout=2)
    assert result["outcome"] == "timed_out" and started == ["slow"] and result["wall_seconds"] < 20
    assert result["usage"] == {"input_tokens": 10, "cached_input_tokens": 3, "cache_write_input_tokens": None,
                               "output_tokens": 5}
    assert (stand_ins.out / "stdout.txt").read_text().endswith('{"type":\n')
    child = int(stand_ins.child.read_text())
    for _ in range(50):  # the kill is sent before the call returns; the process table may take a moment
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail("the delegate's child outlived the time limit")


def test_a_hand_back_that_mentions_a_quota_is_not_a_refusal(stand_ins, tmp_path):
    # Only a run that failed or returned nothing is asked whether it was refused; a reply is never read for it.
    stand_ins.definitions["coding_agents"]["second"]["refusals"] = ["reviewed"]
    result, _ = stand_ins("second", role="reviewer")
    assert result["outcome"] == "handed_back"
    assert delegate.refusal(["usage limit"], "", "warming up\nYou have hit your usage limit.") == "You have hit your usage limit."


def test_changed_paths_are_listed_whole(stand_ins):
    worktree = stand_ins.worktree
    (worktree / "tracked.txt").write_text("one")
    (worktree / "old name.txt").write_text("moved")
    subprocess.run(["git", "-C", str(worktree), "add", "."], check=True)
    subprocess.run(["git", "-C", str(worktree), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit",
                    "-q", "-m", "tracked"], check=True)
    (worktree / "tracked.txt").write_text("two")
    subprocess.run(["git", "-C", str(worktree), "mv", "old name.txt", "new name.txt"], check=True)
    (worktree / "untracked.txt").write_text("new")
    assert sorted(delegate.uncommitted(worktree)) == ["new name.txt", "old name.txt", "tracked.txt", "untracked.txt"]
    assert delegate.uncommitted(worktree.parent) is None


@pytest.mark.parametrize(("action", "changed"), [
    ("pass", []),
    ("pathlib.Path('new.txt').touch()", ["new.txt"]),
    ("pathlib.Path('tracked.txt').write_text('modified')", ["tracked.txt"]),
    ("pathlib.Path('tracked.txt').unlink()", ["tracked.txt"]),
    ("pathlib.Path('dirty/nested.txt').write_text('edited')", ["dirty/nested.txt"]),
    ("pathlib.Path('link').unlink(); pathlib.Path('link').symlink_to('new-target')", ["link"]),
])
def test_read_only_delegate_reports_only_changes_since_start(stand_ins, tmp_path, action, changed):
    worktree = stand_ins.worktree
    (worktree / "tracked.txt").write_text("original")
    subprocess.run(["git", "-C", str(worktree), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(worktree), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "commit", "-qm", "tracked"], check=True)
    (worktree / "dirty").mkdir()
    (worktree / "dirty/nested.txt").write_text("already dirty")
    (worktree / "link").symlink_to("missing-target")
    role = stand_ins.definitions["coding_agents"]["second"]["roles"]["reviewer"]
    role["argv"] = [sys.executable, script(tmp_path / "editor", action + "\nprint(json.dumps({'result': 'reply'}))")]

    result, _ = stand_ins("second", role="reviewer")

    assert result["changed_paths"] == changed
    assert result["commits"] == []
    assert result["unexpected_edits"] == ({"commits": [], "paths": changed} if changed else None)
    assert result["outcome"] == ("unexpected_edits" if changed else "handed_back")
    assert (stand_ins.out / "reply.md").read_text() == "reply"
    if changed:
        assert result["hand_back"] is None
        assert changed[0] in result["detail"]
        row = json.loads((stand_ins.out / "attempt-row-draft.json").read_text())
        assert row["hand_back"] == "failed"


def test_read_only_delegate_reports_new_commits_and_their_paths(stand_ins, tmp_path):
    editor = script(tmp_path / "editor", """import subprocess
pathlib.Path('committed.txt').touch()
subprocess.run(['git', 'add', 'committed.txt'], check=True)
subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid',
                'commit', '-qm', 'new'], check=True)
print(json.dumps({'result': 'reply'}))
""")
    stand_ins.definitions["coding_agents"]["second"]["roles"]["reviewer"]["argv"] = [sys.executable, editor]

    result, _ = stand_ins("second", role="reviewer")

    head = subprocess.check_output(["git", "-C", str(stand_ins.worktree), "rev-parse", "HEAD"], text=True).strip()
    assert result["commits"] == [head]
    assert result["uncommitted"] == []
    assert result["changed_paths"] == ["committed.txt"]
    assert result["unexpected_edits"] == {"commits": [head], "paths": ["committed.txt"]}
    assert result["outcome"] == "unexpected_edits"
    assert head in result["detail"]


@pytest.mark.parametrize(("path", "exit_code"), [
    ("owned/file.txt", 0),
    ("other.txt", 0),
    ("owned-neighbor/file.txt", 1),
])
def test_worker_cli_checks_owned_files_and_directories(stand_ins, tmp_path, path, exit_code):
    editor = script(tmp_path / "editor", f"""path = pathlib.Path({path!r})
path.parent.mkdir(exist_ok=True)
path.write_text('edit')
print(json.dumps({{'result': 'reply'}}))
""")
    stand_ins.definitions["coding_agents"]["second"]["roles"]["worker"]["argv"] = [sys.executable, editor]
    definitions = tmp_path / "delegates.json"
    definitions.write_text(json.dumps(stand_ins.definitions))
    brief = tmp_path / "brief.txt"
    brief.write_text(BRIEF)

    assert delegate.main(["--delegates", str(definitions), "--role", "worker", "--brief", str(brief),
                          "--worktree", str(stand_ins.worktree), "--out", str(stand_ins.out),
                          "--coding-agent", "second", "--model", "model-one", "--effort", "low",
                          "--owned-paths", "./owned/", "./other.txt"]) == exit_code
    result = json.loads((stand_ins.out / "result.json").read_text())
    assert result["unexpected_edits"] == ({"commits": [], "paths": [path]} if exit_code else None)
    assert (stand_ins.worktree / path).read_text() == "edit"


def test_the_acceptance_check_is_run_again_outside_the_delegate_and_both_results_are_reported(stand_ins):
    # The stand-in edits the tree and says it could not run the check, as a sandboxed worker does.
    result, _ = stand_ins("first", check="test -f note.txt")
    assert result["check"] | {"rerun_output": None} == {
        "command": "test -f note.txt", "delegate_reported": "not run", "rerun": "passed", "rerun_exit_code": 0,
        "rerun_output": None}
    assert "Acceptance check: passed" in (stand_ins.out / "brief.txt").read_text()
    # A delegate that says nothing about the check, and a check that fails here, are both reported as such.
    result, _ = stand_ins("third", check="test -f absent.txt")
    assert (result["check"]["delegate_reported"], result["check"]["rerun"]) == ("not stated", "failed")


def test_the_command_line_requires_every_part_of_the_choice_and_exits_by_outcome(stand_ins, tmp_path, capsys):
    definitions = tmp_path / "delegates.json"
    definitions.write_text(json.dumps(stand_ins.definitions))
    brief = tmp_path / "brief.txt"
    brief.write_text(BRIEF)
    common = ["--delegates", str(definitions), "--role", "explorer", "--brief", str(brief),
              "--worktree", str(stand_ins.worktree), "--out", str(stand_ins.out)]
    with pytest.raises(SystemExit) as refused:
        delegate.main([*common, "--coding-agent", "third", "--model", "model-one"])
    assert refused.value.code == 2 and "none has a default: --effort" in capsys.readouterr().err
    assert delegate.main([*common, "--coding-agent", "third", "--model", "model-one", "--effort", "low"]) == 0
    assert "--- hand-back ---\nexplored" in capsys.readouterr().out
    result = json.loads((stand_ins.out / "result.json").read_text())
    assert result["usage"] == {"input_tokens": 15, "cached_input_tokens": 5, "cache_write_input_tokens": None,
                               "output_tokens": 4}
    assert result["models_reported"] is None
    assert delegate.main([*common, "--coding-agent", "silent", "--model", "model-one", "--effort", "low"]) == 1
    assert "Nothing else was started" in capsys.readouterr().out
    result = json.loads((stand_ins.out / "result.json").read_text())
    assert result["outcome"] == "empty_reply"
    assert result["usage"] is None and result["models_reported"] is None


def test_the_previous_delegate_definitions_schema_is_refused(stand_ins, tmp_path):
    definitions = tmp_path / "delegates.json"
    definitions.write_text(json.dumps(stand_ins.definitions | {"schema": "delegates/3"}))
    with pytest.raises(SystemExit, match="expected schema delegates/4, found 'delegates/3'"):
        delegate.main(["--delegates", str(definitions), "--list"])


@pytest.mark.parametrize(("host", "fields", "reply", "outcome", "detail"), [
    ("claude-code", {"is_error": True}, "partial reply", "failed", "is_error=True"),
    ("claude-code", {"subtype": "error"}, "partial reply", "failed", "subtype='error'"),
    ("antigravity", {"status": "ERROR"}, "partial reply", "failed", "status='ERROR'"),
    ("claude-code", {"subtype": "error_max_turns", "is_error": True}, "usage limit", "timed_out", "subtype='error_max_turns'"),
    ("antigravity", {"finishReason": "PRINT_TIMEOUT"}, "partial reply", "timed_out", "finishReason='PRINT_TIMEOUT'"),
    ("claude-code", {"is_error": True}, "You have hit your quota", "refused", "quota"),
    ("claude-code", {"subtype": "SUCCESS", "is_error": 1}, "quota discussion", "handed_back", None),
    ("antigravity", {"status": "success"}, "partial reply", "handed_back", None),
])
def test_structured_exit_zero_outcomes(stand_ins, tmp_path, host, fields, reply, outcome, detail):
    tracked = json.loads(delegate.DELEGATES.read_text())["coding_agents"][host]
    agent = stand_ins.definitions["coding_agents"]["silent"]
    agent.update(outcome_checks=tracked["outcome_checks"], refusals=tracked["refusals"])
    role = agent["roles"]["worker"]
    role["reply"] = tracked["roles"]["worker"]["reply"]
    role["argv"].append(json.dumps(fields | {role["reply"]["stdout_json"]: reply}, indent=2))
    definitions = tmp_path / "delegates.json"
    definitions.write_text(json.dumps(stand_ins.definitions))
    brief = tmp_path / "brief.txt"
    brief.write_text(BRIEF)

    handed_back = outcome == "handed_back"
    assert delegate.main(["--delegates", str(definitions), "--role", "worker", "--brief", str(brief),
                          "--worktree", str(stand_ins.worktree), "--out", str(stand_ins.out),
                          "--coding-agent", "silent", "--model", "model-one", "--effort", "low"]) == (0 if handed_back else 1)
    result = json.loads((stand_ins.out / "result.json").read_text())
    assert result["exit_code"] == 0 and result["outcome"] == outcome
    reply_file = stand_ins.out / "reply.md"
    assert result["hand_back"] == (str(reply_file.resolve()) if handed_back else None)
    assert reply_file.read_text() == reply
    if detail:
        assert detail in result["detail"]
    if outcome == "failed":
        assert "a tool was denied" in result["detail"]
    row = json.loads((stand_ins.out / "attempt-row-draft.json").read_text())
    assert row["hand_back"] == outcome


@pytest.mark.parametrize(("role", "agent", "check", "acceptance"), [
    ("worker", "first", "test -f note.txt", "passed"),
    ("worker", "first", "test -f absent.txt", "failed"),
    ("reviewer", "second", None, None),
])
def test_start_writes_a_draft_in_ledger_schema_order(stand_ins, role, agent, check, acceptance):
    head = subprocess.check_output(["git", "-C", str(stand_ins.worktree), "rev-parse", "HEAD"], text=True).strip()
    result, _ = stand_ins(agent, role=role, check=check)
    assert json.loads((stand_ins.out / "result.json").read_text()) == result
    row = json.loads((stand_ins.out / "attempt-row-draft.json").read_text())
    schema = json.loads((ROOT / "schemas/coding-agent-attempt.schema.json").read_text())
    assert len(row) == 23
    assert list(row) == schema["required"] == list(schema["properties"])
    assert row == {
        "schema": "coding-agent-attempt/3", "issue": None, "kind_of_work": None, "base_commit": head,
        "role": role, "coding_agent": agent.title(), "coding_agent_version": "9.9.9", "model": "model-one",
        "effort": "high", "reason": None, "date": result["date"], "hand_back": "handed_back",
        "acceptance": acceptance, "repairs": 0, "wall_seconds": result["wall_seconds"],
        "blind_preference": None, "outcome": None, "findings": {"confirmed": 0, "rejected": 0} if role == "reviewer" else None,
        "false_report": None, "usage": result["usage"], "brief_design": None, "brief_extent": None,
        "brief_check": True if check else None,
    }


def test_the_tracked_definitions_offer_every_role_on_every_coding_agent():
    definitions = delegate.read_delegates(delegate.DELEGATES)
    assert definitions["schema"] == "delegates/4"
    assert len(definitions["coding_agents"]) == 3
    agents = definitions["coding_agents"]
    argv = agents["claude-code"]["roles"]["worker"]["argv"]
    assert json.loads(argv[argv.index("--settings") + 1]) == {"outputStyle": "default"}
    for host in ("claude-code", "antigravity"):
        checks = agents[host]["outcome_checks"]
        assert set(checks) == {"error_flag", "ok_status", "timeout_fields", "timeout_patterns"}
        assert isinstance(checks["error_flag"], str) and checks["error_flag"]
        status = checks["ok_status"]
        assert set(status) == {"path", "values"} and isinstance(status["path"], str) and status["path"]
        for values in (status["values"], checks["timeout_fields"], checks["timeout_patterns"]):
            assert isinstance(values, list) and values and all(isinstance(value, str) and value for value in values)
        for pattern in checks["timeout_patterns"]:
            re.compile(pattern, re.IGNORECASE)
    for host, agent in agents.items():
        assert set(agent["roles"]) == ROLES
        for role, how in agent["roles"].items():
            argv = how["argv"]
            assert how["read_only"] is (role != "worker")
            assert not set(argv) & {"--ignore-rules", "-s", "workspace-write", "read-only",
                                    "dontAsk", "--allowedTools", "--disallowedTools", "accept-edits", "plan"}
            if host == "codex":
                assert argv[2] == "--dangerously-bypass-approvals-and-sandbox"
                assert ("--ephemeral" in argv) is (role != "worker")
            else:
                mode = "--permission-mode" if host == "claude-code" else "--mode"
                assert argv[argv.index(mode) + 1] == "auto"
            used = set(re.findall(r"\{(\w+)\}", " ".join(how["argv"])))
            assert used <= {"worktree", "model", "effort", "reply_file", "brief"} and {"model", "effort"} <= used
            assert (how["brief"] == "argument") == ("brief" in used) and (how["reply"] == "file") == ("reply_file" in used)
            if how["reply"] != "file":
                assert set(how["reply"]) == {"stdout_json"}
            assert set(how) == {"argv", "brief", "reply", "read_only"}
    for role in ROLES:
        assert (ROOT / ".agents/roles" / f"{role}.md").is_file()


def test_read_only_catches_deleted_git_staged_edit_and_subdir_worktree(stand_ins, tmp_path):
    worktree = stand_ins.worktree
    sub = worktree / "sub"
    sub.mkdir()
    (sub / "s.txt").write_text("v1")
    subprocess.run(["git", "-C", str(worktree), "add", "."], check=True)
    subprocess.run(["git", "-C", str(worktree), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit",
                    "-q", "-m", "sub"], check=True)
    # 1. Subdirectory worktree: editing an already-dirty file must be caught, and --owned-paths resolves relative to sub.
    (sub / "s.txt").write_text("v2")
    edit_sub = script(tmp_path / "edit_sub", "pathlib.Path('s.txt').write_text('v3')\nprint(json.dumps({'result': 'ok'}))")
    stand_ins.definitions["coding_agents"]["edit_sub"] = {
        "name": "EditSub", "version": [sys.executable, "-c", "print('1.0')"], "refusals": [],
        "usage": stand_ins.definitions["coding_agents"]["second"]["usage"],
        "roles": {
            "reviewer": {"argv": [sys.executable, edit_sub], "brief": "stdin", "reply": {"stdout_json": "result"}, "read_only": True},
            "worker": {"argv": [sys.executable, edit_sub], "brief": "stdin", "reply": {"stdout_json": "result"}, "read_only": False},
        },
    }
    res = delegate.start(stand_ins.definitions, coding_agent="edit_sub", model="m", effort="low", role="reviewer",
                         brief=BRIEF, worktree=sub, out=tmp_path / "out_sub_ro", check=None, timeout=None)
    assert res["outcome"] == "unexpected_edits" and res["unexpected_edits"]["paths"] == ["sub/s.txt"]
    res_ok = delegate.start(stand_ins.definitions, coding_agent="edit_sub", model="m", effort="low", role="worker",
                            brief=BRIEF, worktree=sub, out=tmp_path / "out_sub_ok", check=None, timeout=None,
                            owned_paths=["s.txt"])
    assert res_ok["outcome"] == "handed_back" and res_ok["unexpected_edits"] is None

    # 2. Staged-only change preserving MM status and working-tree content must be caught.
    (sub / "s.txt").write_text("staged-a")
    subprocess.run(["git", "-C", str(worktree), "add", "sub/s.txt"], check=True)
    (sub / "s.txt").write_text("work-b")
    restage = script(tmp_path / "restage",
                     "import subprocess\npathlib.Path('sub/s.txt').write_text('staged-c')\n"
                     "subprocess.run(['git', 'add', 'sub/s.txt'], check=True)\n"
                     "pathlib.Path('sub/s.txt').write_text('work-b')\nprint(json.dumps({'result': 'ok'}))")
    stand_ins.definitions["coding_agents"]["restage"] = {
        "name": "Restage", "version": [sys.executable, "-c", "print('1.0')"], "refusals": [],
        "usage": stand_ins.definitions["coding_agents"]["second"]["usage"],
        "roles": {"reviewer": {"argv": [sys.executable, restage], "brief": "stdin", "reply": {"stdout_json": "result"}, "read_only": True}},
    }
    res_staged = delegate.start(stand_ins.definitions, coding_agent="restage", model="m", effort="low", role="reviewer",
                                brief=BRIEF, worktree=worktree, out=tmp_path / "out_staged", check=None, timeout=None)
    assert res_staged["outcome"] == "unexpected_edits" and "sub/s.txt" in res_staged["unexpected_edits"]["paths"]

    # 3. Worker intermediate commit touching an out-of-scope path then reverting it must still be caught.
    inter = script(tmp_path / "inter",
                   "import subprocess\n"
                   "pathlib.Path('outside.txt').write_text('oops')\n"
                   "subprocess.run(['git', 'add', 'outside.txt'], check=True)\n"
                   "subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', 'commit', '-q', '-m', 'c1'], check=True)\n"
                   "subprocess.run(['git', 'rm', '-q', 'outside.txt'], check=True)\n"
                   "pathlib.Path('sub/ok.txt').write_text('good')\n"
                   "subprocess.run(['git', 'add', 'sub/ok.txt'], check=True)\n"
                   "subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', 'commit', '-q', '-m', 'c2'], check=True)\n"
                   "print(json.dumps({'result': 'ok'}))")
    stand_ins.definitions["coding_agents"]["inter"] = {
        "name": "Inter", "version": [sys.executable, "-c", "print('1.0')"], "refusals": [],
        "usage": stand_ins.definitions["coding_agents"]["second"]["usage"],
        "roles": {"worker": {"argv": [sys.executable, inter], "brief": "stdin", "reply": {"stdout_json": "result"}, "read_only": False}},
    }
    res_inter = delegate.start(stand_ins.definitions, coding_agent="inter", model="m", effort="low", role="worker",
                               brief=BRIEF, worktree=worktree, out=tmp_path / "out_inter", check=None, timeout=None,
                               owned_paths=["sub"])
    assert res_inter["outcome"] == "unexpected_edits" and res_inter["unexpected_edits"]["paths"] == ["outside.txt"]

    # 4. Deleted .git during a read-only run must be caught, not silently skipped.
    rm_git = script(tmp_path / "rm_git", "import shutil\nshutil.rmtree('.git')\nprint(json.dumps({'result': 'ok'}))")
    stand_ins.definitions["coding_agents"]["rm_git"] = {
        "name": "RmGit", "version": [sys.executable, "-c", "print('1.0')"], "refusals": [],
        "usage": stand_ins.definitions["coding_agents"]["second"]["usage"],
        "roles": {"reviewer": {"argv": [sys.executable, rm_git], "brief": "stdin", "reply": {"stdout_json": "result"}, "read_only": True}},
    }
    res_rm = delegate.start(stand_ins.definitions, coding_agent="rm_git", model="m", effort="low", role="reviewer",
                            brief=BRIEF, worktree=worktree, out=tmp_path / "out_rm", check=None, timeout=None)
    assert res_rm["outcome"] == "unexpected_edits" and res_rm["unexpected_edits"]["paths"] == ["<worktree no longer a git repository>"]


@pytest.mark.parametrize("bad_path", ["", "/etc/passwd", "../outside"])
def test_invalid_owned_paths_are_rejected(stand_ins, tmp_path, bad_path):
    definitions = tmp_path / "delegates.json"
    definitions.write_text(json.dumps(stand_ins.definitions))
    brief = tmp_path / "brief.txt"
    brief.write_text(BRIEF)
    with pytest.raises(SystemExit) as refused:
        delegate.main(["--delegates", str(definitions), "--role", "worker", "--brief", str(brief),
                       "--worktree", str(stand_ins.worktree), "--out", str(stand_ins.out),
                       "--coding-agent", "second", "--model", "m", "--effort", "low",
                       "--owned-paths", bad_path])
    assert refused.value.code == 2
