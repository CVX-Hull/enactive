"""Read-only, offline MCP endpoint for one bounded packet of original PNGs.

This fixture has no actor, target or execution services. Current tool schemas
are retained so a proposed call can be assessed without making it effective.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from io import BytesIO
import os
from pathlib import Path
import sys

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from PIL import Image

# The host deliberately supplies no PYTHONPATH and can launch from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from harness.computer.protocol import ControlError, canonical, closed, read_json, source
from harness.player.contracts import PlayerError, validate_json
from harness.player_tools import tool_specs

MAX_JSON_BYTES = 1024 * 1024
MAX_PNG_BYTES = 16 * 1024 * 1024
MAX_SOURCES = 30
INSTRUCTIONS = (
    'Offline recorded-screen assessment only. All images and metadata are historical, '
    'including the selected current view within this frozen packet; nothing is captured now. '
    'computer_observe reads the ordered packet and player_source reads one exact member. '
    'Every other tool is a proposal only and is refused, including memory/program reads. '
    'There is no live target, actor authority, input delivery, execution, persistence or game effect.'
)


def load_packet(path: Path) -> tuple[dict, dict[str, bytes]]:
    """Validate once at ingress, then serve only the frozen metadata and bytes."""
    packet = read_json(path, MAX_JSON_BYTES)
    closed(packet, {'current_source_id', 'sources'})
    sources = packet['sources']
    if type(sources) is not list or not 1 <= len(sources) <= MAX_SOURCES:
        raise ControlError('Recorded packet requires 1..30 sources')
    directory = path.parent.resolve() / 'sources'
    if directory.is_symlink() or not directory.is_dir():
        raise ControlError('Recorded sources must be a local directory, not a symlink')
    images = {}
    total = 0
    for metadata in sources:
        source(metadata)
        identity = metadata['source_id']
        if identity in images:
            raise ControlError('Duplicate recorded source ID')
        image_path = directory / f'{identity}.png'
        if image_path.is_symlink() or not image_path.is_file():
            raise ControlError('Recorded PNG must be a local regular file, not a symlink')
        remaining = MAX_PNG_BYTES - total
        if image_path.stat().st_size > remaining:
            raise ControlError('Recorded PNGs exceed 16 MiB')
        with image_path.open('rb') as stream:
            png = stream.read(remaining + 1)
        total += len(png)
        if total > MAX_PNG_BYTES:
            raise ControlError('Recorded PNGs exceed 16 MiB')
        if hashlib.sha256(png).hexdigest() != metadata['sha256']:
            raise ControlError('Recorded PNG hash differs')
        with Image.open(BytesIO(png)) as image:
            if image.format != 'PNG' or image.size != (metadata['width'], metadata['height']):
                raise ControlError('Recorded PNG dimensions or format differ')
            image.verify()
        # Decode as well as checking the PNG structure; never re-encode it.
        with Image.open(BytesIO(png)) as image:
            image.load()
        images[identity] = png
    if type(packet['current_source_id']) is not str or packet['current_source_id'] not in images:
        raise ControlError('Selected current source is not a recorded member')
    return packet, images


def record(log: Path, value: dict) -> None:
    with log.open('a', encoding='utf-8') as stream:
        stream.write(canonical(value) + '\n')


def make_server(packet: dict, images: dict[str, bytes], log: Path) -> Server:
    specs = tool_specs()

    async def list_tools(context, params):
        return types.ListToolsResult(tools=[
            types.Tool(name=name, description=description, input_schema=schema)
            for name, (description, schema) in specs.items()])

    async def call_tool(context, params):
        name = params.name
        args = {} if params.arguments is None else params.arguments
        proposal = name not in ('computer_observe', 'player_source')
        reason = None
        if name not in specs:
            reason = 'Unknown current tool; offline fixture has no execution authority'
        else:
            try:
                validate_json(args, specs[name][1])
            except PlayerError as exc:
                reason = str(exc)
        if reason is None and proposal:
            reason = 'Proposal refused: offline fixture has no execution, live reads or effects'
        if reason is None and name == 'player_source' and args['source_id'] not in images:
            reason = 'Source is not a member of this frozen recorded packet'
        record(log, dict(name=name, arguments=args, proposal=proposal,
                         refusal=reason, read=reason is None))
        if reason is not None:
            return types.CallToolResult(is_error=True, content=[types.TextContent(type='text', text=reason)])
        selected = packet['sources'] if name == 'computer_observe' else [
            metadata for metadata in packet['sources'] if metadata['source_id'] == args['source_id']]
        content = [types.TextContent(type='text', text=canonical(dict(
            historical=True, current_source_id=packet['current_source_id'],
            note='Selected current means only the last selected view in this frozen recorded packet. No capture or effect.')))]
        for metadata in selected:
            content.append(types.TextContent(type='text', text=canonical(dict(
                historical=True, selected_current=metadata['source_id'] == packet['current_source_id'], source=metadata))))
            content.append(types.ImageContent(type='image', data=base64.b64encode(
                images[metadata['source_id']]).decode('ascii'), mime_type='image/png'))
        return types.CallToolResult(content=content)

    server = Server('enactive-recorded-player-fixture', instructions=INSTRUCTIONS,
                    on_list_tools=list_tools, on_call_tool=call_tool,
                    get_tool_input_schema=lambda name: specs[name][1] if name in specs else None)
    server.middleware.clear()
    return server


async def run(packet_path: Path, log: Path) -> None:
    packet, images = load_packet(packet_path)
    server = make_server(packet, images, log)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--pid', type=Path, required=True)
    args = parser.parse_args()
    # A local audit identity, never an actor capability; publish exactly once.
    with args.pid.open('x', encoding='ascii') as stream:
        stream.write(str(os.getpid()))
    record(args.log, dict(event='startup', test_sentinel_inherited='RECORDED_PLAYER_TEST_SENTINEL' in os.environ))
    anyio.run(run, args.packet, args.log)


if __name__ == '__main__':
    main()
