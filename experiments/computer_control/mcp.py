"""Candidate-only MCP; game meaning is absent from every tool contract."""
from __future__ import annotations

import argparse
import base64
from functools import partial
from pathlib import Path
import signal

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .client import ComputerClient
from .protocol import canonical

KEY = dict(type='object', properties=dict(type={'const': 'key'}, key={'type': 'string'},
    modifiers=dict(type='array', items={'enum': ['CTRL', 'ALT', 'SHIFT']}, uniqueItems=True)),
    required=['type', 'key', 'modifiers'], additionalProperties=False)
TEXT = dict(type='object', properties=dict(type={'const': 'text'}, text={'type': 'string'}),
    required=['type', 'text'], additionalProperties=False)
CLICK = dict(type='object', properties=dict(type={'const': 'click'}, x={'type': 'integer', 'minimum': 0},
    y={'type': 'integer', 'minimum': 0}, button={'enum': ['left', 'right']}),
    required=['type', 'x', 'y', 'button'], additionalProperties=False)
WAIT = dict(type='object', properties=dict(type={'const': 'wait'}, seconds=dict(type='number', minimum=0, maximum=2)),
    required=['type', 'seconds'], additionalProperties=False)
EMPTY = dict(type='object', properties={}, additionalProperties=False)
SPECS = {
    'computer_observe': ('Capture the owned target pixels. Metadata is mechanical only; interpret the image yourself. A frame is not proof of task success.', EMPTY),
    'computer_input': ('Choose 1..32 basic operations, in order. Keys are printable ASCII or ENTER/ESC/UP/DOWN/LEFT/RIGHT/TAB/BACKSPACE/SPACE/PAGEUP/PAGEDOWN/HOME/END/DELETE. Text is one SDL UTF8 event up to31 bytes; application consumption is unknown. A click uses full-image output coordinates and requires the capture_id you actually received. Waits are bounded seconds. Stop on partial/unknown, never replay. Delivered means events handed to SDL, not useful effect.',
        dict(type='object', properties=dict(actions=dict(type='array', minItems=1, maxItems=32,
             items={'oneOf': [KEY, TEXT, CLICK, WAIT]}), capture_id=dict(type=['integer', 'null'], minimum=1)),
             required=['actions'], additionalProperties=False)),
    'computer_result': ('Read the original operation receipt and its retained image without input or replay.',
        dict(type='object', properties=dict(operation_id=dict(type='string', pattern='^[0-9a-f]{32}$')),
             required=['operation_id'], additionalProperties=False)),
    'computer_stop': ('Permanently pause further dispatch for this run. This does not save, win or undo input; no automatic rearm.', EMPTY),
}


def make_server(client: ComputerClient) -> Server:
    async def list_tools(context, params):
        return types.ListToolsResult(tools=[types.Tool(name=name, description=description, input_schema=schema)
            for name, (description, schema) in SPECS.items()])

    async def call_tool(context, params):
        try:
            args = params.arguments or {}
            if params.name == 'computer_observe':
                fn = partial(client.execute, observe=True)
            elif params.name == 'computer_input':
                fn = partial(client.execute, args['actions'], capture_id=args.get('capture_id'))
            elif params.name == 'computer_result':
                fn = partial(client.result, args['operation_id'])
            elif params.name == 'computer_stop':
                value = client.stop('Player chose stop')
                return types.CallToolResult(content=[types.TextContent(type='text', text=canonical(value))])
            else:
                raise ValueError('Unknown basic-control tool')
            try:
                value, png = await anyio.to_thread.run_sync(fn, abandon_on_cancel=True)
            except anyio.get_cancelled_exc_class():
                # Fence native dispatch before abandoning a published operation.
                client.stop('MCP operation cancelled; original collection only')
                raise
            content = [types.TextContent(type='text', text=canonical(value))]
            if png is not None:
                content.append(types.ImageContent(type='image', data=base64.b64encode(png).decode(), mime_type='image/png'))
            return types.CallToolResult(content=content)
        except Exception as exc:
            return types.CallToolResult(is_error=True, content=[types.TextContent(type='text', text=canonical(
                dict(error=type(exc).__name__, reason=str(exc)[:600], input_replayed=False)))])

    server = Server('computer-control-proof', version='1.0.0',
        instructions='Only basic computer control is supplied. You own all interpretation, goals, progress, game time, identity, menus, save/load and recovery. Inspect actual pixels/effects. A delivered input is not success. Partial/unknown delivery requires original result collection, never replay or rearm. User Pause/takeover ends input. No source/saves/OS tools are available.',
        on_list_tools=list_tools, on_call_tool=call_tool,
        get_tool_input_schema=lambda name: SPECS[name][1] if name in SPECS else None)
    server.middleware.clear()
    return server


async def run(path: Path) -> None:
    client = ComputerClient(path)
    def stop(signum, frame):
        client.stop('MCP signal cancellation')
        raise KeyboardInterrupt
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    try:
        server = make_server(client)
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    finally:
        client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    options = parser.parse_args()
    anyio.run(run, options.run)
