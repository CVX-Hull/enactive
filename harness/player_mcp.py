"""Project-local stdio MCP adapter; never starts the game or mission runtime."""
from __future__ import annotations

import base64
from pathlib import Path

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .gameplay.contracts import ContractError
from .gameplay.contracts import canonical
from .mission_client import MissionClient
from .player_tools import PlayerTools

ROOT = Path(__file__).resolve().parent.parent


def make_server(player: PlayerTools) -> Server:
    async def list_tools(context, params):
        return types.ListToolsResult(tools=[types.Tool(name=spec.name, description=spec.description,
            input_schema=spec.schema, annotations=types.ToolAnnotations(
                read_only_hint=spec.read_only, destructive_hint=False,
                idempotent_hint=spec.read_only, open_world_hint=False))
            for spec in player.specs.values()])

    async def call_tool(context, params):
        try:
            # The thread runs to its own finite transport deadline. Cancellation
            # never creates a new request ID or replays an admitted operation.
            value, png = await anyio.to_thread.run_sync(player.call, params.name, params.arguments or {})
            content = [types.TextContent(type="text", text=canonical(value))]
            if png is not None:
                content.append(types.ImageContent(type="image", data=base64.b64encode(png).decode("ascii"), mime_type="image/png"))
            return types.CallToolResult(content=content, structured_content=value)
        except (OSError, ValueError, ContractError) as exc:
            return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=str(exc)[:1024])])

    server = Server("enactive-player", version="1.0.0",
        instructions="Use only your explicitly designated role and admitted mission. The deciding player chooses gameplay intent, sources and limits. One advisory actor uses only enactive_reflect_next/submit/source/result, computes only after a durable claimed result, and submits candidate data without game input or memory adoption. The deciding player reads enactive_advice and owns adoption. These procedural roles are not security isolation. Software retains requests and original results; never replay uncertain input. User Pause remains independent.",
        on_list_tools=list_tools, on_call_tool=call_tool,
        get_tool_input_schema=lambda name: player.specs[name].schema if name in player.specs else None)
    server.middleware.clear()  # No optional telemetry/exporters in this local adapter.
    return server


async def run() -> None:
    server = make_server(PlayerTools(MissionClient(ROOT)))
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(run)
