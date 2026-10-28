"""Project-local stdio MCP adapter; never starts the game or mission runtime."""
from __future__ import annotations

import base64
from functools import partial
import math
from pathlib import Path
import time

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .gameplay.contracts import canonical
from .gameplay.contracts import ContractError
from .gameplay.reflection import MAX_REFLECTION_READ_WAIT_SECONDS
from .mission_client import MissionClient
from .player_tools import (
    AdmissionRefusalPresentationError, PlayerTools, UnsubmittedRequest, admission_refusal_feedback,
)
from .player_view import decision_view, snapshot_view

ROOT = Path(__file__).resolve().parent.parent


async def call_player(player: PlayerTools, name: str, arguments: dict, *, advisory_idle_seconds: float = 0):
    """Optional frozen adviser profile waits in software, within original time."""
    end = None
    if name == "enactive_reflect_next" and advisory_idle_seconds:
        status = await anyio.to_thread.run_sync(player.client.status)
        mission = status.get("mission") or {}
        if mission.get("mission_id") != arguments["mission_id"]:
            raise ContractError("Adviser waiting requires its original admitted mission")
        remaining = max(0., mission["deadline"] - time.time())
        end = time.monotonic() + min(advisory_idle_seconds, remaining)
    while True:
        selected = dict(arguments)
        if end is not None:
            selected["wait_seconds"] = min(MAX_REFLECTION_READ_WAIT_SECONDS, max(0., end - time.monotonic()))
        value, image = await anyio.to_thread.run_sync(partial(player.call, name, selected, present_image=False))
        await anyio.lowlevel.checkpoint()
        if end is None or value.get("status") != "idle" or time.monotonic() >= end:
            return value, image
        # Normally the existing passive long poll owns the wait. Yield on an
        # immediate idle response too; never turn an empty queue into model work.
        await anyio.sleep(min(.1, max(0., end - time.monotonic())))


def make_server(player: PlayerTools, *, advisory_idle_seconds: float = 0) -> Server:
    if (type(advisory_idle_seconds) not in (int, float) or not math.isfinite(advisory_idle_seconds)
            or advisory_idle_seconds < 0):
        raise ValueError("Advisory idle wait must be finite and nonnegative")
    async def list_tools(context, params):
        return types.ListToolsResult(tools=[types.Tool(name=spec.name, description=spec.description,
            input_schema=spec.schema, annotations=types.ToolAnnotations(
                read_only_hint=spec.read_only, destructive_hint=False,
                idempotent_hint=spec.read_only, open_world_hint=False))
            for spec in player.model_specs.values()])

    async def call_tool(context, params):
        collection = None
        refusal = None
        value = None
        try:
            arguments, collection = player.model_arguments(params.name, params.arguments or {})
            # The thread runs to its own finite transport deadline. Cancellation
            # never creates a new request ID or replays an admitted operation.
            value, png = await call_player(player, params.name, arguments, advisory_idle_seconds=advisory_idle_seconds)
            refusal = admission_refusal_feedback(value)
            if collection is not None and (value.get("transport") == "uncertain" or value.get("settled") is False):
                # The assigned identity survives pending work/lost reply even when the
                # immediate snapshot is unavailable. This is collection-only,
                # never proof of admission, delivery or permission to replay.
                value = dict(value, original_collection=collection)
            # A cancelled worker may still finish later. It cannot establish
            # presentation; only this synchronous response-building path can.
            value, png = player.present_image(params.name, value, png)
            value = decision_view(params.name, value)
            content = [types.TextContent(type="text", text=canonical(value))]
            if png is not None:
                content.append(types.ImageContent(type="image", data=base64.b64encode(png).decode("ascii"), mime_type="image/png"))
            return types.CallToolResult(content=content)
        except UnsubmittedRequest as exc:
            # This type escapes proven new mutation preparation or advisory
            # preflight, outside SDK staging/submission and presentation.
            value = dict(error=str(exc)[:1024], submission="not_submitted",
                next_step="Follow the error's supported next step or explicitly correct the selected arguments "
                    "for a new decision under original limits; "
                    "do not collect this unsubmitted request. No authority is granted.")
            return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=canonical(value))])
        except Exception as exc:
            player.invalidate_image_presentation()
            if isinstance(exc, AdmissionRefusalPresentationError):
                refusal = exc.feedback
            if refusal is not None:
                feedback = dict(refusal, error="Admission refusal presentation failed")
                try:
                    current = value.get("next_snapshot") if isinstance(value, dict) else None
                    if current is None:
                        current, _ = await anyio.to_thread.run_sync(player.snapshot)
                    feedback["next_snapshot"] = snapshot_view(current)
                except Exception as snapshot_error:
                    feedback["snapshot_error"] = str(snapshot_error)[:1024]
                return types.CallToolResult(is_error=True,
                    content=[types.TextContent(type="text", text=canonical(feedback))])
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
        except BaseException:
            player.invalidate_image_presentation()
            raise

    server = Server("enactive-player", version="6.1.0",
        instructions="Use only your designated role and admitted mission. Choose gameplay intent, exact returned snapshot/source and finite execution limits. Snapshots and proof receipts are read-only: grants_authority=false is not a failed adoption or an execution refusal. Follow the actual result, next_needed_decision and active phase; the writer checks each request. Software assigns request IDs and bounded collection waits; do not supply request_id or wait_seconds. Pending/uncertain delivery requires original result collection, never resubmission. User Pause remains independent. An adviser uses only enactive_reflect_next/submit/source/result, computes only after a durable claim and submits candidate data without input or memory adoption. The player reads advice and owns adoption. Roles are procedural, not security isolation.",
        on_list_tools=list_tools, on_call_tool=call_tool,
        get_tool_input_schema=lambda name: player.model_specs[name].schema if name in player.model_specs else None)
    server.middleware.clear()  # No optional telemetry/exporters in this local adapter.
    return server


async def run(*, advisory_idle_seconds: float = 0) -> None:
    server = make_server(PlayerTools(MissionClient(ROOT)), advisory_idle_seconds=advisory_idle_seconds)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--advisory-idle-seconds", type=float, default=0)
    options = parser.parse_args()
    anyio.run(partial(run, advisory_idle_seconds=options.advisory_idle_seconds))
