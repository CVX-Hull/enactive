"""Offline MCP double for player-host/1 tests, using the maintained Python MCP server.

Shared by the adapter node tests and the adapter-agnostic contract suite."""
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
# Environment inventory for the contract suite's credential-isolation case.
PID.with_name(PID.name + '.env').write_text(json.dumps(dict(os.environ)))
if len(sys.argv) > 3:
    time.sleep(float(sys.argv[3]))
# Publish owned process identity before third-party startup can consume a deadline.
import asyncio
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ImageContent, TextContent
from pydantic import WithJsonSchema
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


# Isolated union-schema feedback fixture; production tool schemas are discovered
# through the separate composition integration lane.
MEMORY_INTENT = {"anyOf": [
    {"type": "object", "required": ["entry_type", "entry"], "properties": {
        "entry_type": {"const": "work"},
        "entry": {"type": "object", "properties": {
            "stage": {"type": "string", "maxLength": 128},
            "available": {"type": "array", "items": {"type": "object", "properties": {
                "subject": {"type": "string", "pattern": "^[a-z_]+$"}}}}}}}},
    {"type": "object", "required": ["entry_type", "entry"], "properties": {
        "entry_type": {"const": "fact"}, "entry": {"type": "object", "required": ["value"],
            "properties": {"value": {"type": "string"}}}}}
]}


@server.tool()
async def fixture_remember(snapshot_id: str, intent: Annotated[dict, WithJsonSchema(MEMORY_INTENT)]) -> CallToolResult:
    record(dict(tool="fixture_remember", snapshot_id=snapshot_id, intent=intent))
    fail = intent["entry"].get("stage") == "mcp-error"
    return CallToolResult(content=[TextContent(type="text", text=(
        'Validation failed for tool "fixture_remember":\nfixture MCP refusal' if fail else "retained fixture"))], isError=fail)


OPERATION = "1" * 32
SESSION = "2" * 32
ACTOR = "3" * 32


def handoff_receipt(mode):
    issued = dict(schema="player-handoff/1", operation_id=OPERATION, session=SESSION,
        actor_id=ACTOR, context_id="4" * 32, context_sha256="5" * 64,
        sealed_wall=123456.0, grants_authority=False)
    value = dict(schema="computer-operation/1", operation_id=OPERATION,
        session=SESSION, actor_id=ACTOR, kind="handoff", status="sealed",
        created_wall=123450.0, deadline_monotonic=123456.0, receipts=[], source=None,
        remaining=dict(seconds=10), reason=None, handoff=issued)
    if mode == "refused":
        return dict(schema="computer-operation/1", operation_id=OPERATION,
            session=SESSION, actor_id=ACTOR, kind="handoff", status="refused", handoff=None)
    if mode in ("pending", "another-pending"):
        value.update(status="pending", handoff=None)
        if mode == "another-pending":
            value["operation_id"] = "6" * 32
    if mode == "transport-uncertain":
        return dict(schema="player-transport/1", operation_id=OPERATION,
            session=SESSION, actor_id=ACTOR, kind="handoff", status="unknown",
            reason="Submission response unavailable; collect the original operation")
    if mode == "not-admitted":
        return dict(error="Correct this draft; no submission")
    if mode == "foreign":
        issued["session"] = "6" * 32
    if mode == "old":
        issued["schema"] = "player-handoff/0"
    if mode == "legacy":
        return dict(presentation_schema="player-view/5", operation_id=OPERATION,
            response=dict(operation=dict(kind="handoff", state="completed",
                result=dict(schema="mission/11", grants_authority=False))))
    if mode == "context":
        issued["context_sha256"] = "invalid"
    if mode == "actor":
        value["actor_id"] = "6" * 32
    if mode == "operation":
        value["operation_id"] = "6" * 32
    if mode == "session":
        value["session"] = "6" * 32
    if mode == "authority":
        issued["grants_authority"] = True
    if mode == "sealed-wall":
        issued["sealed_wall"] = 0
    return value


@server.tool()
async def player_handoff(ids: list[str] | None = None, summary: str = "", mode: str = "complete") -> CallToolResult:
    record(dict(tool="player_handoff", mode=mode))
    value = handoff_receipt(mode)
    content = [TextContent(type="text", text="{" if mode == "malformed" else json.dumps(value))]
    if mode == "extra-text":
        content.append(TextContent(type="text", text="Supplemental player-visible context"))
    return CallToolResult(content=content, isError=mode in ("error", "not-admitted"))


@server.tool()
async def computer_result(operation_id: str, mode: str = "complete") -> CallToolResult:
    record(dict(tool="computer_result", mode=mode))
    return CallToolResult(content=[TextContent(type="text", text="Formatting failed" if mode == "plain-error"
        else json.dumps(handoff_receipt(mode)))], isError=mode == "plain-error")

server.run(transport="stdio")
