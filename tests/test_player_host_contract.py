"""Adapter-agnostic conformance for `player-host/2` (docs/contracts/player-host.md).

Each listed adapter is driven only through the contract surface: argv modes,
files, environment, stdin, stdout JSONL, stderr and exit status. A scripted
OpenAI-compatible provider and an MCP double stand in for the model and the
actor's tools. Passing is interface evidence only; it qualifies no model,
provider, latency or gameplay outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
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
from tools.campaign_player import HostEvents

ROOT = Path(__file__).resolve().parents[1]
MCP_DOUBLE = ROOT / "tests" / "fixtures" / "player_host_mcp.py"
CREDENTIAL_ENV = "FIXTURE_PROVIDER_KEY"
CREDENTIAL = "contract-credential-4f1c9a7e"
ALLOWANCE = 4
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


def route(adapter: Adapter, base_url: str, *, schema="player-host/2", max_requests=ALLOWANCE) -> dict:
    """The contract envelope around the adapter-owned model."""
    return dict(schema=schema, service_tier="default", api_key_env=CREDENTIAL_ENV, max_requests=max_requests,
                max_context_images=4, context_image_block=1, request_timeout_seconds=10, model=adapter.model(base_url))


# ---------------------------------------------------------------- reference provider

def sse(*chunks) -> bytes:
    return ("".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode()


def text_response(text: str) -> tuple:
    return ("sse", sse(
        dict(id="ref", model="ref-backend", choices=[dict(index=0, delta=dict(role="assistant", content=text), finish_reason=None)]),
        dict(id="ref", model="ref-backend", choices=[dict(index=0, delta={}, finish_reason="stop")],
             usage=dict(prompt_tokens=11, completion_tokens=5, total_tokens=16))))


def tool_response(name: str, arguments: dict) -> tuple:
    call = dict(index=0, id="call-0", type="function", function=dict(name=name, arguments=json.dumps(arguments)))
    return ("sse", sse(
        dict(id="ref", model="ref-backend", choices=[dict(index=0, delta=dict(role="assistant", tool_calls=[call]), finish_reason=None)]),
        dict(id="ref", model="ref-backend", choices=[dict(index=0, delta={}, finish_reason="tool_calls")],
             usage=dict(prompt_tokens=11, completion_tokens=5, total_tokens=16))))


def http_response(status: int, body: dict) -> tuple:
    return ("http", status, json.dumps(body).encode())


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
            self.end_headers()
            self.wfile.write(step[2])
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(step[1])


# ---------------------------------------------------------------- host harness

class Hosted:
    """One adapter invocation with the driver's launch shape and its own file set."""

    def __init__(self, adapter, directory: Path, provider: Provider, *, enabled_tools=("observe",), effort="off"):
        self.adapter, self.directory, self.provider, self.effort = adapter, directory, provider, effort
        self.paths = {name: directory / name for name in ("route.json", "mcp.json", "context.txt", "prompt.txt", "final.txt",
                                                          "host.jsonl", "host-stderr.log", "mcp-log", "mcp-pid")}
        self.paths["route.json"].write_text(json.dumps(route(adapter, provider.base_url)))
        self.paths["mcp.json"].write_text(json.dumps(self.mcp(enabled_tools)))
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
                "--context", str(self.paths["context.txt"]), "--model", "fixture", "--effort", self.effort,
                "--timeout-seconds", timeout_seconds, "-o", str(self.paths["final.txt"])]

    def start(self, arguments: list[str] | None = None, *, timeout_seconds="30") -> "Hosted":
        arguments = ["run", *self.flags(timeout_seconds)] if arguments is None else arguments
        environment = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), LANG="en_US.UTF-8", **{CREDENTIAL_ENV: CREDENTIAL})
        with self.paths["host.jsonl"].open("x") as output, self.paths["host-stderr.log"].open("x") as errors, \
                self.paths["prompt.txt"].open() as prompt:
            self.process = subprocess.Popen([*self.adapter.argv, *arguments], cwd=ROOT, env=environment, stdin=prompt,
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
        reader = HostEvents(self.paths["host.jsonl"], ALLOWANCE)
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
    for schema in ("pi-player-host/4", "player-host/0", "player-host/2"):
        result = run_mode(adapter, ["validate", *validation_files(envelope=route(adapter, "http://127.0.0.1:9/v1", schema=schema))])
        assert result.returncode != 0, schema


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
    hosted = host_factory([text_response("The mission report.")])
    assert hosted.start().wait() == 0
    assert hosted.final().strip() == "The mission report."
    events = hosted.events()
    kinds = [event["type"] for event in events]
    assert kinds[0] == "host-start" and kinds.count("host-start") == 1
    assert events[0]["schema"] == "player-host/2" and events[0]["telemetry_version"] == 2
    assert kinds[-1] == "settled" and kinds.count("settled") == 1
    accounting = hosted.accounted()
    assert accounting["accounting_complete"] is True
    assert accounting["attempts_charged"] == len(hosted.provider.requests) == 1
    assert accounting["settled"]["reason"] == "completed" and accounting["settled"]["ok"] is True
    assert CREDENTIAL in hosted.provider.requests[0]["authorization"]
    assert hosted.provider.requests[0]["path"].endswith("/chat/completions")
    assert process_gone(hosted.mcp_pid())


def test_handoff_settles_once_leaves_final_unchanged_and_closes_the_mcp_child(adapter, host_factory):
    hosted = host_factory([tool_response("player_handoff", dict(ids=[], summary="Retain current context")),
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
    assert accounting["attempts_charged"] == len(hosted.provider.requests) == 1
    assert process_gone(hosted.mcp_pid())


def test_credential_reaches_neither_output_nor_the_mcp_child(adapter, host_factory):
    detail = dict(error=dict(message=f"rejected credential {CREDENTIAL}", type="forbidden"))
    hosted = host_factory([http_response(403, detail)])
    assert hosted.start().wait() != 0
    settled = hosted.settled()
    assert settled["ok"] is False
    assert hosted.provider.requests, "the refusal must have been provoked by a real provider request"
    for name in ("host.jsonl", "host-stderr.log"):
        assert CREDENTIAL not in hosted.paths[name].read_text(), name
    assert hosted.final() == "reserved"
    environment = json.loads(hosted.paths["mcp-pid"].with_name("mcp-pid.env").read_text())
    assert CREDENTIAL_ENV not in environment
    assert all(CREDENTIAL not in value for value in environment.values())
    assert set(environment) <= {"PATH", "LANG", "__CF_USER_TEXT_ENCODING", "LC_CTYPE"}
    assert process_gone(hosted.mcp_pid())


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
    assert settled["ok"] is False and settled["reason"] != "completed"
    assert hosted.final() == "reserved"
    accounting = hosted.accounted()
    assert accounting["accounting_complete"] is True and accounting["settled"]["requests"] == len(hosted.provider.requests)
    if hosted.paths["mcp-pid"].exists():
        assert process_gone(hosted.mcp_pid())
    cleanup = close_group(hosted.process)
    assert cleanup["process_absent"] and cleanup["group_absent"] and cleanup["signals"] == []
