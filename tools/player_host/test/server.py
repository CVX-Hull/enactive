"""Offline boundary fixture using the maintained Python MCP server."""
import asyncio
import json
import os
from pathlib import Path
import sys
import time
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ImageContent, TextContent

# MCP 2.x deliberately diverts fd1 away from its wire. Keep an owned duplicate
# solely to inject invalid bytes in the transport-error negative fixture.
CORRUPTION_FD = os.dup(1)
LOG = Path(sys.argv[1])
PID = Path(sys.argv[2])
PID.write_text(str(os.getpid()))
if len(sys.argv) > 3:
    time.sleep(float(sys.argv[3]))
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

server.run(transport="stdio")
