"""Offline boundary fixture using the maintained Python MCP server."""
import json
import os
from pathlib import Path
import sys
import time
from typing import Annotated

# MCP 2.x deliberately diverts fd1 away from its wire. Keep an owned duplicate
# solely to inject invalid bytes in the transport-error negative fixture.
CORRUPTION_FD = os.dup(1)
LOG = Path(sys.argv[1])
PID = Path(sys.argv[2])
PID.write_text(str(os.getpid()))
if len(sys.argv) > 3:
    time.sleep(float(sys.argv[3]))
# Publish owned process identity before third-party startup can consume a deadline.
import asyncio
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ImageContent, TextContent
from pydantic import WithJsonSchema
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from harness.player_tools import tool_specs
server = MCPServer("offline-player-fixture", instructions="Use only the admitted fixture tools.")
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ioAAAAASUVORK5CYII="

def record(value):
    with LOG.open("a") as stream:
        stream.write(json.dumps(value) + "\n")

@server.tool()
async def observe(fail: bool = False) -> CallToolResult:
    record({"tool": "observe", "fail": fail})
    value = {"original_collection": {"operation_id": "original-op", "source": "source-1", "cursor": 7}}
    return CallToolResult(content=[TextContent(type="text", text="x" * 30001), TextContent(type="text", text=json.dumps(value)), ImageContent(type="image", data=PNG, mimeType="image/png")], structuredContent=value, isError=fail)

@server.tool()
async def mutate(mode: str, index: int = 0) -> str:
    record({"tool": "mutate", "phase": "start", "index": index, "secret_inherited": "UNRELATED_HOST_SECRET" in os.environ})
    if mode == "malformed":
        os.write(CORRUPTION_FD, b"invalid JSON fixture corruption\n")
        await asyncio.sleep(30)
    if mode == "drop":
        os._exit(11)
    if mode == "wait":
        await asyncio.sleep(30)
    await asyncio.sleep(0.03)
    record({"tool": "mutate", "phase": "end", "index": index})
    return "done"

@server.tool()
async def integer(value: int) -> int:
    record({"tool": "integer", "value": value})
    return value


MEMORY_INTENT = next(spec.schema["properties"]["intent"] for spec in tool_specs()
    if spec.name == "enactive_remember")


@server.tool()
async def enactive_remember(snapshot_id: str, intent: Annotated[dict, WithJsonSchema(MEMORY_INTENT)]) -> CallToolResult:
    record(dict(tool="enactive_remember", snapshot_id=snapshot_id, intent=intent))
    fail = intent["entry"].get("stage") == "mcp-error"
    return CallToolResult(content=[TextContent(type="text", text=(
        'Validation failed for tool "enactive_remember":\nfixture MCP refusal' if fail else "retained fixture"))], isError=fail)


def handoff_receipt(mode):
    issued = dict(schema="mission/11", record_type="Handoff", grants_authority=False,
        handoff_id="issued-handoff", mission_id="mission", original_player_id="original",
        post_pause_source_id="paused-source", successor_role="player", unfinished_work_ids=[])
    mission = dict(mission_id="mission", actor_id="original", player_id="original",
        phase="handoff", pause_cause="internal_handoff", lease_owner=None, active_operation=None,
        progress_operation_id="issued-handoff", current_source=dict(observation_id="paused-source"))
    value = dict(presentation_schema="player-view/5", transport="delivered", settled=True,
        operation_id="issued-handoff", next_snapshot=dict(mission=mission),
        response=dict(status="accepted", operation=dict(kind="handoff", state="completed",
            request_id="issued-handoff", result=issued)))
    if mode == "refused":
        return dict(error="Correct this draft", submission="not_submitted")
    if mode == "pending":
        value["settled"] = False
        value["response"]["operation"]["state"] = "running"
    if mode in ("transport-uncertain", "transport-no-snapshot"):
        value.update(transport="uncertain", settled=False, response=None,
            reason="Submission response unavailable; collect the original operation",
            original_collection=dict(tool="enactive_result", arguments=dict(
                mission_id="mission", operation_id="issued-handoff")))
        if mode == "transport-no-snapshot":
            value.pop("next_snapshot")
            value["snapshot_error"] = "Current context unavailable"
    if mode == "not-admitted":
        value.update(submission="not_admitted", response=None)
    if mode == "foreign":
        issued["mission_id"] = "foreign"
    if mode == "old":
        issued["schema"] = "mission/10"
    if mode == "source":
        issued["post_pause_source_id"] = None
    if mode == "newer":
        mission["current_source"]["observation_id"] = "newer-read-only-source"
    if mode == "actor":
        mission["actor_id"] = "other-actor"
    if mode == "operation":
        value["operation_id"] = "other-operation"
    if mode == "uncertain":
        return dict(error="Presentation failed after staging", original_collection=dict(
            tool="enactive_result", arguments=dict(mission_id="mission", operation_id="issued-handoff")))
    return value


@server.tool()
async def enactive_handoff(snapshot_id: str, intent: dict, mode: str = "complete") -> CallToolResult:
    record(dict(tool="enactive_handoff", mode=mode))
    value = handoff_receipt(mode)
    return CallToolResult(content=[TextContent(type="text", text="{" if mode == "malformed" else json.dumps(value))], isError=mode in ("error", "uncertain"))


@server.tool()
async def enactive_result(mission_id: str, operation_id: str, mode: str = "complete") -> CallToolResult:
    record(dict(tool="enactive_result", mode=mode))
    return CallToolResult(content=[TextContent(type="text", text="Formatting failed" if mode == "plain-error"
        else json.dumps(handoff_receipt(mode)))], isError=mode == "plain-error")

server.run(transport="stdio")
