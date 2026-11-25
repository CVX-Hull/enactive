"""Adapter-agnostic conformance for `player-host/12` (docs/contracts/player-host.md).

Each listed adapter is driven only through the contract surface: argv modes,
files, environment, stdin, stdout JSONL, stderr and exit status. A scripted
OpenAI-compatible provider and an MCP double stand in for the model and the
actor's tools. Passing is interface evidence only; it qualifies no model,
provider, latency or gameplay outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

import pytest

from harness.computer.launch import close_group
from tools import campaign_run
from tools.campaign_player import HostEvents

ROOT = Path(__file__).resolve().parents[1]
MCP_DOUBLE = ROOT / "tests" / "fixtures" / "player_host_mcp.py"
CREDENTIAL_ENV = "FIXTURE_PROVIDER_KEY"
CREDENTIAL = "contract-credential-4f1c9a7e"
@dataclass(frozen=True)
class Adapter:
    """One listed adapter. The suite appends only a mode and contract flags to
    `argv`. The adapter owns its closed route `model`; `model(base_url)` serves the
    reference OpenAI-compatible provider double below. An adapter for another wire
    format supplies its own provider double through the same steps before listing."""
    name: str
    argv: list[str]
    model: Callable[[str], dict]
    missing: Callable[[], str | None]


def node_package_missing(argv: list[str]) -> str | None:
    if shutil.which(argv[0]) is None and not Path(argv[0]).is_file():
        return f"adapter executable {argv[0]} is unavailable"
    package = Path(argv[-1]).parent
    if not (package / "node_modules").is_dir():
        return f"{package}/node_modules is not installed"
    return None


CURRENT_ARGV = [shutil.which("node") or "node", str(ROOT / "tools" / "player_host" / "run.mjs")]
ADAPTERS = [Adapter(
    name="player_host",
    argv=CURRENT_ARGV,
    model=lambda base_url: dict(id="fixture", name="fixture", api="openai-completions", provider="fixture",
                                baseUrl=base_url, input=["text", "image"], reasoning=False,
                                cost=dict(input=0, output=0, cacheRead=0, cacheWrite=0), contextWindow=10000, maxTokens=100),
    missing=lambda: node_package_missing(CURRENT_ARGV),
)]


@pytest.fixture(params=ADAPTERS, ids=lambda adapter: adapter.name)
def adapter(request) -> Adapter:
    reason = request.param.missing()
    if reason:
        pytest.skip(reason)
    return request.param


#: What a request with no cost record counts for in these routes, and what each reference response reports.
UNPRICED_REQUEST_USD = "0.25"
RESPONSE_COST_USD = 0.004


def route(adapter: Adapter, base_url: str, *, schema="player-host/12", spend_limit_usd="100") -> dict:
    """The contract envelope around the adapter-owned model."""
    return dict(schema=schema, service_tier="default", api_key_env=CREDENTIAL_ENV,
                spend_limit_usd=spend_limit_usd, unpriced_request_usd=UNPRICED_REQUEST_USD,
                max_context_images=4, context_image_block=1, context_reserve_tokens=512, context_cut=None,
                request_timeout_seconds=10, model=adapter.model(base_url), endpoint_costs=None,
                recall=dict(model=adapter.model(base_url),every=5,unpriced_request_usd=UNPRICED_REQUEST_USD,endpoint_costs=None))


# ---------------------------------------------------------------- reference provider

def sse(*chunks) -> bytes:
    return ("".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode()


def text_response(text: str) -> tuple:
    return ("sse", sse(
        dict(id="ref", model="ref-backend", choices=[dict(index=0, delta=dict(role="assistant", content=text), finish_reason=None)]),
        dict(id="ref", model="ref-backend", choices=[dict(index=0, delta={}, finish_reason="stop")],
             usage=dict(prompt_tokens=11, completion_tokens=5, total_tokens=16, cost=RESPONSE_COST_USD))))


def tool_response(name: str, arguments: dict, *, cost: float = RESPONSE_COST_USD) -> tuple:
    if name == 'player_finish': arguments = {'intent':'Report the task disposition',**arguments}
    call = dict(index=0, id="call-0", type="function", function=dict(name=name, arguments=json.dumps(arguments)))
    return ("sse", sse(
        dict(id="ref", model="ref-backend", choices=[dict(index=0, delta=dict(role="assistant", tool_calls=[call]), finish_reason=None)]),
        dict(id="ref", model="ref-backend", choices=[dict(index=0, delta={}, finish_reason="tool_calls")],
             usage=dict(prompt_tokens=11, completion_tokens=5, total_tokens=16, cost=cost))))


def http_response(status: int, body: dict, headers=None) -> tuple:
    return ("http", status, json.dumps(body).encode(), headers or {})


HANG = ("hang",)


class Provider(ThreadingHTTPServer):
    """Scripted `/v1/chat/completions` on 127.0.0.1; one scripted step per request."""
    daemon_threads = True

    def __init__(self, steps):
        super().__init__(("127.0.0.1", 0), Handler)
        self.steps = list(steps)
        self.requests: list[dict] = []
        self.lock = threading.Lock()
        self.first_request = threading.Event()
        self.release = threading.Event()
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/v1"

    def take(self, record: dict) -> tuple:
        with self.lock:
            self.requests.append(record)
            step = self.steps.pop(0) if self.steps else http_response(500, dict(error=dict(message="script exhausted")))
        self.first_request.set()
        return step

    def stop(self) -> None:
        self.release.set()
        self.shutdown()
        self.server_close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        step = self.server.take(dict(path=self.path, authorization=self.headers.get("Authorization", ""), body=body))
        if step[0] == "hang":
            self.server.release.wait(60)
            return
        if step[0] == "http":
            self.send_response(step[1])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(step[2])))
            for name, value in step[3].items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(step[2])
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(step[1])
        if step[0] == "stalled-sse":
            self.wfile.flush()
            self.server.release.wait(60)


# ---------------------------------------------------------------- host harness

class Hosted:
    """One adapter invocation with the driver's launch shape and its own file set."""

    def __init__(self, adapter, directory: Path, provider: Provider, *, enabled_tools=("observe",), effort="off", spend_limit_usd="100", finish_reserve_usd="0"):
        self.adapter, self.directory, self.provider, self.effort = adapter, directory, provider, effort
        self.finish_reserve_usd = finish_reserve_usd
        self.paths = {name: directory / name for name in ("route.json", "delivered-knowledge.json", "mcp.json", "context.txt", "prompt.txt", "final.txt",
                                                          "host.jsonl", "host-stderr.log", "mcp-log", "mcp-pid")}
        self.route = route(adapter, provider.base_url, spend_limit_usd=spend_limit_usd)
        self.paths["route.json"].write_text(json.dumps(self.route))
        self.paths["mcp.json"].write_text(json.dumps(self.mcp(enabled_tools)))
        self.paths["delivered-knowledge.json"].write_text(json.dumps(dict(schema="delivered-knowledge/3",version=None,commit=None,repository_id=None,coverage=None,articles=[],facts=[],
                                                                                history=dict(replaced={},ended=[],retracted=[]))))
        self.paths["context.txt"].write_text("Frozen player guide")
        self.paths["prompt.txt"].write_text("Offline mission")
        self.paths["final.txt"].write_text("reserved")
        self.process: subprocess.Popen | None = None

    def mcp(self, enabled_tools) -> dict:
        return dict(command=sys.executable, args=[str(MCP_DOUBLE), str(self.paths["mcp-log"]), str(self.paths["mcp-pid"])],
                    cwd=str(self.directory), enabled=True, required=True, enabled_tools=list(enabled_tools),
                    startup_timeout_sec=15, tool_timeout_sec=5)

    def flags(self, timeout_seconds="30") -> list[str]:
        return ["--config", str(self.paths["route.json"]), "--mcp-config", str(self.paths["mcp.json"]),
                "--context", str(self.paths["context.txt"]), "--prompt", str(self.paths["prompt.txt"]),
                "--session", "2" * 32, "--actor-id", "3" * 32, "--pending-control-id", "none", "--delivered-knowledge", str(self.paths["delivered-knowledge.json"]), "--finish-reserve-usd", self.finish_reserve_usd, "--model", "fixture", "--effort", self.effort,
                "--timeout-seconds", timeout_seconds, "-o", str(self.paths["final.txt"])]

    def start(self, arguments: list[str] | None = None, *, timeout_seconds="30") -> "Hosted":
        arguments = ["run", *self.flags(timeout_seconds)] if arguments is None else arguments
        environment = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), LANG="en_US.UTF-8", **{CREDENTIAL_ENV: CREDENTIAL})
        with self.paths["host.jsonl"].open("x") as output, self.paths["host-stderr.log"].open("x") as errors:
            self.process = subprocess.Popen([*self.adapter.argv, *arguments], cwd=ROOT, env=environment, stdin=subprocess.PIPE,
                                            stdout=output, stderr=errors, start_new_session=True)
        return self

    def wait(self, seconds: float = 40) -> int:
        try:
            return self.process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            pytest.fail(f"adapter did not exit within {seconds} seconds:\n{self.paths['host.jsonl'].read_text()}")

    def events(self) -> list[dict]:
        return [json.loads(line) for line in self.paths["host.jsonl"].read_text().splitlines() if line]

    def settled(self) -> dict:
        last = self.events()[-1]
        assert last["type"] == "settled", last
        return last

    def final(self) -> str:
        return self.paths["final.txt"].read_text()

    def mcp_pid(self) -> int:
        return int(self.paths["mcp-pid"].read_text())

    def accounted(self) -> dict:
        reader = HostEvents(self.paths["host.jsonl"])
        try:
            return reader.finish()
        finally:
            reader.close()

    def teardown(self) -> None:
        if self.process is not None and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait()


@pytest.fixture
def host_factory(adapter, tmp_path):
    created: list[tuple[Hosted, Provider]] = []

    def make(steps, **options) -> Hosted:
        provider = Provider(steps)
        hosted = Hosted(adapter, tmp_path, provider, **options)
        created.append((hosted, provider))
        return hosted

    yield make
    for hosted, provider in created:
        hosted.teardown()
        provider.stop()


def process_gone(pid: int, seconds: float = 5) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def run_mode(adapter, arguments, **kwargs) -> subprocess.CompletedProcess:
    environment = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), LANG="en_US.UTF-8")
    return subprocess.run([*adapter.argv, *arguments], cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=30, **kwargs)


# ---------------------------------------------------------------- validate mode

@pytest.fixture
def validation_files(adapter, tmp_path):
    # Port 9 (discard) is never contacted: validation is offline and credential-free.
    def write(*, envelope=None, mcp=None) -> list[str]:
        paths = (tmp_path / "route.json", tmp_path / "mcp.json")
        template = route(adapter, "http://127.0.0.1:9/v1") if envelope is None else envelope
        table = dict(command=sys.executable, args=[str(MCP_DOUBLE), "log", "pid"], cwd=str(tmp_path), enabled=True,
                     required=True, enabled_tools=["observe"], startup_timeout_sec=15, tool_timeout_sec=5) if mcp is None else mcp
        paths[0].write_text(json.dumps(template))
        paths[1].write_text(json.dumps(table))
        return ["--config", str(paths[0]), "--mcp-config", str(paths[1]), "--model", "fixture", "--effort", "off"]
    return write


def test_validate_accepts_reference_route_and_mcp_table_silently(adapter, validation_files):
    result = run_mode(adapter, ["validate", *validation_files()])
    assert result.returncode == 0 and result.stdout == ""


def test_validate_rejects_old_route_schema(adapter, validation_files):
    for schema in ("pi-player-host/7", *(f"player-host/{version}" for version in (0, 1, 2, 3, 7, 8, 9, 10))):
        result = run_mode(adapter, ["validate", *validation_files(envelope=route(adapter, "http://127.0.0.1:9/v1", schema=schema))])
        assert result.returncode != 0, schema


def test_validate_accepts_a_closed_context_cut(adapter, validation_files):
    envelope = dict(route(adapter, "http://127.0.0.1:9/v1"),
                    context_cut={"high_mark": 6000, "low_mark": 2000, "min_free": 10})
    result = run_mode(adapter, ["validate", *validation_files(envelope=envelope)])
    assert result.returncode == 0 and result.stdout == ""


@pytest.mark.parametrize("cut", [False, {}, {"high_mark": 6000, "low_mark": 2000},
    {"high_mark": 6000, "low_mark": 2000, "min_free": 10, "extra": 1},
    {"high_mark": 6000, "low_mark": 6000, "min_free": 10},
    {"high_mark": 6000, "low_mark": 2000, "min_free": 0},
    {"high_mark": 6000, "low_mark": 2000, "min_free": 1.5}])
def test_validate_rejects_invalid_context_cut(adapter, validation_files, cut):
    envelope = dict(route(adapter, "http://127.0.0.1:9/v1"), context_cut=cut)
    assert run_mode(adapter, ["validate", *validation_files(envelope=envelope)]).returncode != 0


def test_validate_rejects_disabled_mcp_table(adapter, validation_files, tmp_path):
    table = dict(command=sys.executable, args=[], cwd=str(tmp_path), enabled=False, enabled_tools=["observe"],
                 startup_timeout_sec=15, tool_timeout_sec=5)
    assert run_mode(adapter, ["validate", *validation_files(mcp=table)]).returncode != 0


def test_validate_requires_a_mode_word(adapter, validation_files):
    assert run_mode(adapter, validation_files()).returncode != 0
    assert run_mode(adapter, ["unknown-mode", *validation_files()]).returncode != 0


# ---------------------------------------------------------------- run mode

@pytest.mark.parametrize("case", ["missing", "unknown", "repeated", "no-mode"])
def test_run_with_invalid_arguments_settles_unsuccessfully(adapter, host_factory, case):
    hosted = host_factory([])
    flags = hosted.flags()
    arguments = {
        "missing": ["run", *flags[:-2]],
        "unknown": ["run", *flags, "--bogus", "1"],
        "repeated": ["run", *flags, "--effort", "off"],
        "no-mode": flags,
    }[case]
    assert hosted.start(arguments).wait() != 0
    # Refusal shape: one unsuccessful settlement, no host-start, so accounting is incomplete.
    assert [event["type"] for event in hosted.events()] == ["settled"]
    assert hosted.settled()["ok"] is False
    assert hosted.accounted()["accounting_complete"] is False
    assert hosted.provider.requests == [] and hosted.final() == "reserved"


def test_oversized_input_is_refused_before_any_provider_request(adapter, host_factory):
    hosted = host_factory([text_response("must never be requested")])
    hosted.paths["context.txt"].write_bytes(b"x" * (1024 * 1024 + 1))
    assert hosted.start().wait() != 0
    assert hosted.settled()["ok"] is False
    assert hosted.provider.requests == [] and hosted.final() == "reserved"


def test_completed_run_reports_final_text_and_accountable_telemetry(adapter, host_factory):
    hosted = host_factory([tool_response("player_finish", dict(disposition="task_complete", report="The mission report.", source_ids=[], control_id=None))])
    assert hosted.start().wait() == 0
    assert hosted.final().strip() == "The mission report."
    events = hosted.events()
    kinds = [event["type"] for event in events]
    assert kinds[0] == "host-start" and kinds.count("host-start") == 1
    assert events[0]["schema"] == "player-host/12" and events[0]["telemetry_version"] == 12
    assert kinds[-1] == "settled" and kinds.count("settled") == 1
    accounting = hosted.accounted()
    assert accounting["accounting_complete"] is True
    assert accounting["observed_attempts"] == len(hosted.provider.requests) == 1
    assert (accounting["reported_usd"], accounting["unpriced_requests"], accounting["spent_usd"]) == ("0.004", 0, "0.004")
    assert accounting["settled"]["reason"] == "task_complete" and accounting["settled"]["ok"] is True
    assert CREDENTIAL in hosted.provider.requests[0]["authorization"]
    assert hosted.provider.requests[0]["path"].endswith("/chat/completions")
    assert process_gone(hosted.mcp_pid())


def test_a_listed_newer_knowledge_version_is_delivered_and_an_entry_that_does_not_verify_never_stops_the_host(adapter, host_factory, tmp_path):
    """The optional `--knowledge-updates` list (docs/contracts/player-host.md, A newer version during play): one
    entry that verifies and two that do not. The host delivers the first as its own delimited message in the
    next request it builds, records the others as refused and finishes the run."""
    import hashlib
    hosted = host_factory([tool_response("integer", dict(value=7)),
                           tool_response("player_finish", dict(disposition="task_complete", report="Done.", source_ids=[], control_id=None))],
                          enabled_tools=("integer",))
    position = dict(session="s01", actor="001", step=1, order=[1, "001", 1])
    shared = dict(tags=[], scope=dict(game="example"), branch_relation=None, lifecycle_state="active", needs_review=False,
                  stale_citations=[], condition_unverified=False, unverified_branch=False, links=[], backlinks=[], shadowed_by=[],
                  contradicted_by=[])
    version = dict(schema="delivered-knowledge/3", version="v1", commit="c" * 40, repository_id="d" * 40,
                   coverage=dict(schema="curator-coverage/2", session="s01", actor="001", last_step=20),
                   articles=[dict(id="article-a", revision="article-a@v1", title="A subject", lead="A useful lead. More.",
                                  body=[dict(text="A claim.", facts=["fact-a"])], **shared, last_confirmed=position)],
                   facts=[dict(id="fact-a", claim_kind="mechanic", evidence_basis="observed", text="A claim.", **shared,
                               cited_by_articles=["article-a"], citation_source_ids=["2" * 32 + "-1"], seen=position)],
                   history=dict(replaced={}, ended=[], retracted=[]))
    data = json.dumps(version).encode()
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "v1.json").write_bytes(data)
    (tmp_path / "knowledge" / "v2.json").write_bytes(data)
    entry = dict(schema="knowledge-update-entry/1", version="v1", commit=version["commit"], repository_id=version["repository_id"],
                 file="knowledge/v1.json", sha256=hashlib.sha256(data).hexdigest(), coverage=version["coverage"])
    updates = tmp_path / "knowledge-updates.jsonl"
    # In the order the host tries them, newest first: v2's file names v1, the unparsable line is no entry.
    updates.write_text("".join(json.dumps(row) + "\n" for row in (entry, dict(entry, version="v2", file="knowledge/v2.json"))) + "{not json\n")
    assert hosted.start(["run", *hosted.flags(), "--knowledge-updates", str(updates)]).wait() == 0
    events = hosted.events()
    deliveries = [e for e in events if e["type"] == "knowledge-delivery" and e["kind"] == "update"]
    refused = [(e["version"], e["reason"]) for e in deliveries if e["outcome"] == "refused"]
    assert len(refused) == 2 and set(refused) == {(None, "invalid-entry"), ("v2", "entry-mismatch")}
    delivered, = (e for e in deliveries if e["outcome"] == "delivered")
    assert (delivered["version"], delivered["previous_version"], delivered["coverage"], delivered["receiving_player_request_id"]) == (
        "v1", None, version["coverage"], "request-1")
    assert (delivered["delivered_knowledge_schema"], delivered["grants_authority"], delivered["index_ids"]) == ("delivered-knowledge/3", False, ["article-a"])
    begin, body, end = delivered["text"].split("\n")
    assert begin.startswith("BEGIN FALLIBLE KNOWLEDGE UPDATE (v1)") and end == "END FALLIBLE KNOWLEDGE UPDATE (v1)"
    assert json.loads(body)["index"] == [dict(id="article-a", title="A subject", index="A useful lead")]
    first, second = (json.loads(request["body"])["messages"] for request in hosted.provider.requests)
    texts = lambda messages: [m["content"] if isinstance(m["content"], str) else "".join(p.get("text", "") for p in m["content"] or [])
                              for m in messages if m["role"] == "user"]
    assert texts(first).count(delivered["text"]) == 1 and second[:len(first)] == first
    assert hosted.settled()["reason"] == "task_complete" and hosted.accounted()["accounting_complete"] is True
    # The flag is closed like the others: repeated, it refuses before any request.
    repeated = run_mode(adapter, ["run", *hosted.flags(), "--knowledge-updates", str(updates), "--knowledge-updates", str(updates)])
    assert repeated.returncode != 0 and len(hosted.provider.requests) == 2


def test_a_hung_knowledge_updates_fifo_does_not_prevent_the_host_cli_from_exiting(adapter, host_factory, tmp_path):
    """R-REGRESSION (B1): a stalled filesystem read of `--knowledge-updates` (simulated by a FIFO with no writer)
    is abandoned on its timeout and must not keep the Node host CLI process alive after settlement."""
    fifo = tmp_path / "hung-knowledge-updates.jsonl"
    os.mkfifo(fifo)
    hosted = host_factory([tool_response("player_finish", dict(disposition="task_complete", report="Done.", source_ids=[], control_id=None))])
    try:
        proc = hosted.start(["run", *hosted.flags(), "--knowledge-updates", str(fifo)])
        code = proc.wait(15)
        assert code == 0
        assert hosted.settled()["reason"] == "task_complete"
        assert hosted.accounted()["accounting_complete"] is True
    finally:
        try:
            fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
            os.close(fd)
        except OSError:
            pass


def test_the_dollar_limit_refuses_the_next_request_and_the_receipt_totals_follow_the_trace(adapter, host_factory):
    """A run with a $0.01 limit and responses reporting $0.004 each: the third takes the total to $0.012, so the
    fourth request is never sent. The driver's reading of the trace and the receipt's record agree with it."""
    hosted = host_factory([tool_response("integer", dict(value=7)) for _ in range(4)], enabled_tools=("integer",), spend_limit_usd="0.01")
    hosted.route["unpriced_request_usd"] = "0.001"
    hosted.paths["route.json"].write_text(json.dumps(hosted.route))
    assert hosted.start().wait() != 0
    settled = hosted.settled()
    assert (settled["ok"], settled["reason"], settled["requests"]) == (False, "spend-limit", 3)
    assert (settled["spent_usd"], settled["unpriced_requests"]) == ("0.012", 0)
    assert len(hosted.provider.requests) == 3
    counted = [(e["request_id"], e["counted_cost_usd"], e["cost_counted_as"], e["spent_usd"])
               for e in hosted.events() if e["type"] == "response-complete"]
    assert counted == [("request-1", "0.004", "provider-reported", "0.004"), ("request-2", "0.004", "provider-reported", "0.008"),
                       ("request-3", "0.004", "provider-reported", "0.012")]
    actor = hosted.accounted()
    assert (actor["observed_attempts"], actor["reported_usd"], actor["unpriced_requests"], actor["spent_usd"],
            actor["spend_complete"]) == (3, "0.012", 0, "0.012", True)
    receipt = campaign_run.accounting(dict(spend_limit_usd="0.01"), hosted.route, actor, True)
    assert receipt == dict(spend_limit_usd="0.01", reported_usd="0.012", unpriced_requests=0, unpriced_request_usd="0.001", unpriced_recall_requests=0,unpriced_recall_request_usd="0.25",
                           spent_usd="0.012", observed_attempts=3, observed_recall_attempts=0, spend_complete=True)
    # The overshoot is less than one response: the limit was not yet reached when the third request was sent.
    assert Decimal(receipt["spent_usd"]) - Decimal(receipt["spend_limit_usd"]) < Decimal("0.004")


@pytest.mark.parametrize("repeat_stall", [False, True])
def test_incomplete_stream_recovery_in_same_host(adapter, host_factory, repeat_stall):
    # Valid-looking tool arguments were already parsed in the Talty timeout.
    # Keep the connection open before a finish reason, price or terminal SSE event.
    partial = tool_response("integer", {"value": 99})[1].split(b"\n\n", 1)[0] + b"\n\n"
    stall = ("stalled-sse", partial)
    finish = tool_response("player_finish", dict(disposition="task_complete", report="Recovered", source_ids=[], control_id=None))
    hosted = host_factory([tool_response("integer", {"value": 7}), stall, stall if repeat_stall else finish],
                          enabled_tools=("integer",))
    hosted.route["request_timeout_seconds"] = 1
    hosted.paths["route.json"].write_text(json.dumps(hosted.route))
    code = hosted.start().wait()
    assert (code != 0) == repeat_stall
    events = hosted.events()
    assert [e["arguments"]["value"] for e in events if e["type"] == "tool-start" and e["tool"] == "integer"] == [7]
    bodies = [r["body"] for r in hosted.provider.requests]
    assert len(bodies) == 3 and bodies[1] == bodies[2]
    attempts = [e for e in events if e["type"] == "response-complete"]
    assert [e["request_id"] for e in attempts] == ["request-1", "request-2", "request-3"]
    assert attempts[1]["response_progress"]["tool_argument_bytes"] > 0
    assert attempts[1]["reported_cost_usd"] is None
    assert hosted.settled()["reason"] == ("request-timeout" if repeat_stall else "task_complete")
    accounting = hosted.accounted()
    assert accounting["observed_attempts"] == 3 and accounting["unpriced_requests"] == 1 + repeat_stall
    assert accounting["spend_complete"] and len([e for e in events if e["type"] == "mcp-connected"]) == 1


def test_a_successful_response_without_a_cost_stops_the_run_and_counts_at_the_bound(adapter, host_factory):
    unpriced = ("sse", sse(dict(id="ref", model="ref-backend", choices=[dict(index=0, delta=dict(role="assistant", content="hello"),
                                                                             finish_reason="stop")])))
    hosted = host_factory([unpriced, text_response("must never be requested")])
    assert hosted.start().wait() != 0
    assert hosted.settled()["reason"] == "cost-unreported" and len(hosted.provider.requests) == 1
    actor = hosted.accounted()
    assert (actor["reported_usd"], actor["unpriced_requests"], actor["spent_usd"]) == ("0", 1, "0")


def test_plain_report_requires_a_direct_finish_call(adapter, host_factory):
    hosted = host_factory([text_response('This is only narration.'),
        tool_response('player_finish', dict(disposition='cannot_continue', report='Cannot continue.', source_ids=[], control_id=None))])
    assert hosted.start().wait() == 0
    assert hosted.settled()['reason'] == 'cannot_continue'
    assert hosted.final().strip() == 'Cannot continue.'
    assert len(hosted.provider.requests) == 2
    assert len([event for event in hosted.events() if event['type'] == 'player-finish']) == 1


def test_external_stop_uses_live_partial_jsonl_and_direct_finish_origin(adapter, host_factory):
    command = dict(schema='player-control/1', id='a' * 32, session='2' * 32, actor_id='3' * 32, type='orderly_stop')
    hosted = host_factory([tool_response('player_finish', dict(disposition='external_stop_complete',
        report='Automation stopped.', source_ids=[], control_id=command['id']))])
    hosted.start()
    line = (json.dumps(command) + '\n').encode()
    hosted.process.stdin.write(line[:17]); hosted.process.stdin.flush()
    hosted.process.stdin.write(line[17:] + line); hosted.process.stdin.flush()
    assert hosted.wait() == 0
    assert hosted.settled()['reason'] == 'external_stop_complete'
    assert hosted.settled()['control_id'] == command['id']
    assert len([event for event in hosted.events() if event['type'] == 'control-accepted']) == 1
    assert process_gone(hosted.mcp_pid())


def test_control_eof_before_settlement_is_unsuccessful(adapter, host_factory):
    hosted = host_factory([HANG])
    hosted.start()
    assert hosted.provider.first_request.wait(30)
    pid = hosted.mcp_pid()
    hosted.process.stdin.close()
    assert hosted.wait() != 0
    assert hosted.settled()['reason'] == 'control-eof'
    assert hosted.final() == 'reserved'
    assert process_gone(pid)


def test_handoff_settles_once_leaves_final_unchanged_and_closes_the_mcp_child(adapter, host_factory):
    hosted = host_factory([tool_response("player_handoff", dict(summary="Retain current context")),
                           text_response("must never be requested")], enabled_tools=("player_handoff",))
    assert hosted.start().wait() == 0
    handoffs = [event for event in hosted.events() if event["type"] == "handoff"]
    assert len(handoffs) == 1
    handoff = handoffs[0]
    assert (handoff["actor_id"], handoff["session"], handoff["handoff_id"]) == ("3" * 32, "2" * 32, "1" * 32)
    assert handoff["context_id"] == "4" * 32 and handoff["context_sha256"] == "5" * 64
    assert handoff["grants_authority"] is False
    settled = hosted.settled()
    assert settled["ok"] is True and settled["reason"] == "handoff"
    assert hosted.final() == "reserved"
    accounting = hosted.accounted()
    assert accounting["accounting_complete"] is True and accounting["handoff"]["handoff_id"] == "1" * 32
    assert accounting["observed_attempts"] == len(hosted.provider.requests) == 1
    assert process_gone(hosted.mcp_pid())


def test_credential_reaches_neither_output_nor_the_mcp_child(adapter, host_factory):
    detail = dict(error=dict(message=f"rejected credential {CREDENTIAL}", type="forbidden"))
    hosted = host_factory([http_response(403, detail)])
    assert hosted.start().wait() != 0
    settled = hosted.settled()
    assert settled["ok"] is False
    assert len(hosted.provider.requests) == 1
    refusal = next(e for e in hosted.events() if e["type"] == "provider-refusal")
    assert (refusal["refusal_class"], refusal["provider_name"]) == ("auth", None)
    assert not any(e["type"] == "provider-retry" for e in hosted.events())
    for name in ("host.jsonl", "host-stderr.log"):
        assert CREDENTIAL not in hosted.paths[name].read_text(), name
    assert hosted.final() == "reserved"
    environment = json.loads(hosted.paths["mcp-pid"].with_name("mcp-pid.env").read_text())
    assert CREDENTIAL_ENV not in environment
    assert all(CREDENTIAL not in value for value in environment.values())
    assert set(environment) <= {"PATH", "LANG", "__CF_USER_TEXT_ENCODING", "LC_CTYPE"}
    assert process_gone(hosted.mcp_pid())


@pytest.mark.parametrize("suppress", [False, True], ids=["retry", "suppressed"])
def test_upstream_403_uses_the_shared_retry_through_the_cli(adapter, host_factory, suppress):
    """R-KEY-LEAK and R-OVERSPEND: redacted refusal fields and bounded attempt accounting."""
    private_message, private_raw = "private prompt echoed by fixture", "private endpoint response"
    refusal = dict(code=403, message=f"{private_message} {CREDENTIAL}",
                   metadata=dict(provider_name="Fixture Endpoint", provider_code="endpoint_refused", raw=private_raw))
    headers = {"retry-after-ms": "0", **({"x-should-retry": "false"} if suppress else {})}
    finish = tool_response("player_finish", dict(disposition="task_complete", report="Done.", source_ids=[], control_id=None))
    hosted = host_factory([http_response(403, refusal, headers), finish])
    assert hosted.start().wait() == int(suppress)
    assert len(hosted.provider.requests) == (1 if suppress else 2)
    events = hosted.events()
    diagnostic = next(e for e in events if e["type"] == "provider-refusal")
    assert (diagnostic["request_id"], diagnostic["refusal_class"], diagnostic["provider_name"], diagnostic["provider_error_code"]) == (
        "request-1", "upstream-provider", "Fixture Endpoint", "endpoint_refused")
    eligible = [e["retry_class"] for e in events if e["type"] == "provider-retry" and e["stage"] == "eligible"]
    assert eligible == ([] if suppress else ["provider-403-failover"])
    if not suppress:
        assert hosted.provider.requests[0]["body"] == hosted.provider.requests[1]["body"]
    accounting = hosted.accounted()
    assert accounting["accounting_complete"] is True and accounting["unpriced_requests"] == 1
    for name in ("host.jsonl", "host-stderr.log"):
        output = hosted.paths[name].read_text()
        assert all(value not in output for value in (CREDENTIAL, private_message, private_raw))


def test_spend_notice_crosses_the_work_budget_threshold_and_keeps_prior_messages(adapter, host_factory):
    """R-OVERSPEND and R-REGRESSION: halving-step finish guidance before the reserve with stable request prefixes."""
    # Work budget = $2.00 above $0.10 finish reserve (15% warning threshold = $0.30, above $0.25 unpriced bound).
    calls = [
        tool_response("integer", dict(value=7), cost=1.696),
        tool_response("integer", dict(value=7), cost=0.004),
        tool_response("integer", dict(value=7), cost=0.004),
    ]
    finish = tool_response("player_finish", dict(disposition="task_complete", report="Done.", source_ids=[], control_id=None))
    hosted = host_factory([*calls, finish], enabled_tools=("integer",), spend_limit_usd="2.10", finish_reserve_usd="0.10")
    assert hosted.start().wait() == 0
    events = hosted.events()
    assert events[0]["telemetry_version"] == 12
    notices = [e for e in events if e["type"] == "tail-notice"]
    # $2.00 work budget -> $0.30 after $1.70 crosses 100% ($0.30) on request-3;
    # $0.296 on request-4 stays above 50% ($0.15) and still admits ordinary work ($1.704 + $0.10 + $0.25 < $2.10).
    assert [(e["request_id"], e["kinds"]) for e in notices] == [("request-3", ["spend-limit"])]
    payloads = [json.loads(request["body"])["messages"] for request in hosted.provider.requests]
    assert all(after[:len(before)] == before for before, after in zip(payloads, payloads[1:]))
    first = payloads[2][-1]["content"][0]["text"]
    assert "about $0.3 of work budget remains" in first and "ending reserve" in first and "Wrap up with player_finish" in first


def test_sigterm_cancels_closes_the_mcp_child_and_leaves_no_process_group(adapter, host_factory):
    hosted = host_factory([HANG])
    hosted.start()
    assert hosted.provider.first_request.wait(30), "the host never reached the provider"
    mcp_pid = hosted.mcp_pid()
    os.kill(hosted.process.pid, signal.SIGTERM)
    assert hosted.wait() != 0
    settled = hosted.settled()
    assert settled["ok"] is False and settled["reason"] == "cancelled"
    assert hosted.final() == "reserved"
    assert process_gone(mcp_pid)
    cleanup = close_group(hosted.process)
    assert cleanup["process_absent"] and cleanup["group_absent"] and cleanup["signals"] == []


def test_deadline_settles_unsuccessfully_within_the_original_allowance(adapter, host_factory):
    hosted = host_factory([HANG])
    started = time.monotonic()
    assert hosted.start(timeout_seconds="5").wait(30) != 0
    assert time.monotonic() - started < 25
    settled = hosted.settled()
    assert settled["ok"] is False and settled["reason"] != "task_complete"
    assert hosted.final() == "reserved"
    accounting = hosted.accounted()
    assert accounting["accounting_complete"] is True and accounting["settled"]["requests"] == len(hosted.provider.requests)
    if hosted.paths["mcp-pid"].exists():
        assert process_gone(hosted.mcp_pid())
    cleanup = close_group(hosted.process)
    assert cleanup["process_absent"] and cleanup["group_absent"] and cleanup["signals"] == []
