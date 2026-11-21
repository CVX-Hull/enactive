"""The delegate call starts the one delegate the lead names and reports what happened, with stand-in commands.

No coding agent is started here. Each stand-in is a small script that records that it ran and then behaves as
one of the cases the lead has to be told about: a hand-back, a start that fails, an empty reply, a refusal, a
sandbox that cannot run the acceptance check. The tracked definitions are read only to see that each coding
agent offers every role and that every placeholder they use is one the call fills.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

from tools import delegate

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"worker", "reviewer", "explorer", "locator"}
BRIEF = "Role: worker, named for the test\nGoal: write note.txt\n"


def script(path: Path, body: str) -> str:
    path.write_text(f"import os, pathlib, sys\n{body}\n", encoding="utf-8")
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
    bodies = {
        # Writes its reply to the file it is told, like a coding agent with a last-message option, and edits the tree.
        "first": "NAME = 'first'\n" + mark + "brief = sys.stdin.read()\npathlib.Path('note.txt').write_text('written')\n"
                 "pathlib.Path(sys.argv[1]).write_text('model ' + sys.argv[2] + ' effort ' + sys.argv[3] + ' key ' "
                 "+ os.environ.get('SECRET_KEY', 'absent') + '\\n' + brief + '\\nAcceptance check: not run\\n')",
        # Prints its reply; takes the brief as an argument.
        "second": "NAME = 'second'\n" + mark + "print('reviewed: ' + sys.argv[1][:40])",
        "third": "NAME = 'third'\n" + mark + "print('explored')",
        "silent": "NAME = 'silent'\n" + mark + "print('a tool was denied', file=sys.stderr)",
        "refusing": "NAME = 'refusing'\n" + mark + "print('You have hit your usage limit', file=sys.stderr)\nsys.exit(1)",
        "crashing": "NAME = 'crashing'\n" + mark + "print('boom', file=sys.stderr)\nsys.exit(3)",
        "slow": "NAME = 'slow'\n" + mark + "import time\ntime.sleep(30)",
    }
    commands = {name: script(tmp_path / name, body) for name, body in bodies.items()}
    version = [sys.executable, "-c", "print('9.9.9')"]

    def agent(name, argv, brief="stdin", reply="stdout"):
        role = {"argv": argv, "brief": brief, "reply": reply}
        return {"name": name, "version": version, "refusals": ["usage limit", "sign ?in"],
                "roles": {"worker": role, "reviewer": role, "explorer": role, "locator": role}}

    definitions = {"schema": "delegates/1", "role_instruction": "You are the {role}.", "drop_environment": ["SECRET_KEY"],
                   "coding_agents": {
                       "first": agent("First", [sys.executable, commands["first"], "{reply_file}", "{model}", "{effort}"], reply="file"),
                       "second": agent("Second", [sys.executable, commands["second"], "{brief}"], brief="argument"),
                       "third": agent("Third", [sys.executable, commands["third"]]),
                       "silent": agent("Silent", [sys.executable, commands["silent"]]),
                       "refusing": agent("Refusing", [sys.executable, commands["refusing"]]),
                       "crashing": agent("Crashing", [sys.executable, commands["crashing"]]),
                       "slow": agent("Slow", [sys.executable, commands["slow"]]),
                       "absent": agent("Absent", [str(tmp_path / "no-such-command")]),
                       "partly": {"name": "Partly", "version": version, "refusals": [],
                                  "roles": {"worker": {"unavailable": "no start that works, 1 January 2026"}}}}}

    def start(coding_agent, role="worker", **options):
        options = {"model": "model-one", "effort": "high", "brief": BRIEF, "check": None, "timeout": None} | options
        result = delegate.start(definitions, coding_agent=coding_agent, role=role, worktree=worktree,
                                out=tmp_path / "out", **options)
        ran = started.read_text().split() if started.exists() else []
        return result, ran

    start.worktree, start.out, start.definitions = worktree, tmp_path / "out", definitions
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


@pytest.mark.parametrize(("coding_agent", "outcome", "detail", "ran"), [
    ("absent", "failed_start", "is not on the path", []),
    ("silent", "empty_reply", "a tool was denied", ["silent"]),
    ("refusing", "refused", "usage limit", ["refusing"]),
    ("crashing", "failed", "exit code 3: boom", ["crashing"]),
    ("partly", "unavailable", "no start that works", []),
])
def test_a_run_with_no_hand_back_is_reported_as_what_it_was_and_nothing_else_is_started(stand_ins, coding_agent, outcome, detail, ran):
    result, started = stand_ins(coding_agent)
    assert result["outcome"] == outcome and detail in result["detail"] and result["hand_back"] is None
    assert started == ran


def test_a_run_past_its_time_limit_is_reported_and_stopped(stand_ins):
    result, started = stand_ins("slow", timeout=1)
    assert result["outcome"] == "timed_out" and started == ["slow"] and result["wall_seconds"] < 20


def test_a_long_hand_back_that_mentions_a_quota_is_not_a_refusal(stand_ins):
    assert delegate.refusal(["usage limit"], 0, "The usage limit note in the page is wrong. " * 20, "", "") is None
    assert delegate.refusal(["usage limit"], 0, "You have hit your usage limit.", "", "") == "You have hit your usage limit."


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
    assert delegate.main([*common, "--coding-agent", "silent", "--model", "model-one", "--effort", "low"]) == 1
    assert "Nothing else was started" in capsys.readouterr().out
    assert json.loads((stand_ins.out / "result.json").read_text())["outcome"] == "empty_reply"


def test_the_tracked_definitions_offer_every_role_on_every_coding_agent():
    definitions = delegate.read_delegates(delegate.DELEGATES)
    assert len(definitions["coding_agents"]) == 3
    for agent in definitions["coding_agents"].values():
        assert set(agent["roles"]) == ROLES
        for how in agent["roles"].values():
            if "unavailable" in how:
                continue
            used = set(re.findall(r"\{(\w+)\}", " ".join(how["argv"])))
            assert used <= {"worktree", "model", "effort", "reply_file", "brief"} and {"model", "effort"} <= used
            assert (how["brief"] == "argument") == ("brief" in used) and (how["reply"] == "file") == ("reply_file" in used)
    for role in ROLES:
        assert (ROOT / ".agents/roles" / f"{role}.md").is_file()
