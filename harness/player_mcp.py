"""Project-local stdio MCP adapter; never starts the game or mission runtime."""
from __future__ import annotations

import base64
from pathlib import Path

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .gameplay.contracts import canonical
from .mission_client import MissionClient
from .player_tools import PlayerTools, UnsubmittedRequest
from .player_view import decision_view

ROOT = Path(__file__).resolve().parent.parent


def make_server(player: PlayerTools) -> Server:
    async def list_tools(context, params):
        return types.ListToolsResult(tools=[types.Tool(name=spec.name, description=spec.description,
            input_schema=spec.schema, annotations=types.ToolAnnotations(
                read_only_hint=spec.read_only, destructive_hint=False,
                idempotent_hint=spec.read_only, open_world_hint=False))
            for spec in player.model_specs.values()])

    async def call_tool(context, params):
        collection = None
        try:
            arguments, collection = player.model_arguments(params.name, params.arguments or {})
            # The thread runs to its own finite transport deadline. Cancellation
            # never creates a new request ID or replays an admitted operation.
            value, png = await anyio.to_thread.run_sync(player.call, params.name, arguments)
            value = decision_view(params.name, value)
            content = [types.TextContent(type="text", text=canonical(value))]
            if png is not None:
                content.append(types.ImageContent(type="image", data=base64.b64encode(png).decode("ascii"), mime_type="image/png"))
            return types.CallToolResult(content=content)
        except UnsubmittedRequest as exc:
            # This type escapes pure ordinary composition or advisory preflight,
            # before SDK staging/submission. No original operation exists.
            value = dict(error=str(exc)[:1024], submission="not_submitted",
                next_step="Correct the selected arguments for a new decision under original limits; "
                    "do not collect this unsubmitted request. No authority is granted.")
            return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=canonical(value))])
        except Exception as exc:
            # This is the outer invocation boundary: even an unexpected Python
            # formatting error after staging must retain the assigned identity.
            # Cancellation/BaseException still propagates without another call.
            if collection is not None:
                # Keep the assigned identity even if dispatch, projection or
                # serialization fails. Collection may be unavailable when the
                # failure preceded staging; the error proves neither delivery
                # nor nondelivery.
                value = dict(error=str(exc)[:1024], original_collection=collection,
                    delivery="Not proved by this error; collect the original if submission is uncertain")
                return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=canonical(value))])
            return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=str(exc)[:1024])])

    server = Server("enactive-player", version="5.2.2",
        instructions="Use only your designated role and admitted mission. Choose gameplay intent, exact returned snapshot/source and finite execution limits. Snapshots and proof receipts are read-only: grants_authority=false is not a failed adoption or an execution refusal. Follow the actual result, next_needed_decision and active phase; the writer checks each request. Software assigns request IDs and bounded collection waits; do not supply request_id or wait_seconds. Pending/uncertain delivery requires original result collection, never resubmission. User Pause remains independent. An adviser uses only enactive_reflect_next/submit/source/result, computes only after a durable claim and submits candidate data without input or memory adoption. The player reads advice and owns adoption. Roles are procedural, not security isolation.",
        on_list_tools=list_tools, on_call_tool=call_tool,
        get_tool_input_schema=lambda name: player.model_specs[name].schema if name in player.model_specs else None)
    server.middleware.clear()  # No optional telemetry/exporters in this local adapter.
    return server


async def run() -> None:
    server = make_server(PlayerTools(MissionClient(ROOT)))
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(run)
