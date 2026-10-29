"""Current stdio MCP adapter to one actor's loopback control/playing service."""
from __future__ import annotations

import argparse
import base64
from pathlib import Path
import signal

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .computer.protocol import canonical
from .player_client import PlayerClient
from .player_tools import tool_specs


def make_server(client: PlayerClient) -> Server:
    specs=tool_specs()

    async def list_tools(context,params):
        return types.ListToolsResult(tools=[types.Tool(name=name,description=description,input_schema=schema)
                                          for name,(description,schema) in specs.items()])

    async def call_tool(context,params):
        if params.name not in specs:
            return types.CallToolResult(is_error=True,content=[types.TextContent(type='text',text='Unknown current tool')])
        args={} if params.arguments is None else params.arguments
        try:
            try:
                value,png,error=await anyio.to_thread.run_sync(lambda:client.call(params.name,args),abandon_on_cancel=True)
            except anyio.get_cancelled_exc_class():
                client.stop('MCP operation cancelled; original collection only')
                raise
            content=[types.TextContent(type='text',text=canonical(value))]
            if png is not None:
                content.append(types.ImageContent(type='image',data=base64.b64encode(png).decode('ascii'),mime_type='image/png'))
            return types.CallToolResult(is_error=error,content=content)
        except Exception as exc:
            return types.CallToolResult(is_error=True,content=[types.TextContent(type='text',text=canonical(
                dict(schema='player-error/1',error=type(exc).__name__,reason=str(exc)[:600],input_replayed=False)))])

    server=Server('enactive-player',version='2.0.0',
        instructions=('Only basic computer control is authoritative. You own all game interpretation, goals, menus, identity, time, '
        'tactics, save/load and success. Memory/procedures/advice are optional fallible player data. Use actual pixels. '
        'Delivered input is not useful success. Partial/unknown input ends dispatch; collect original IDs, never replay/rearm. '
        'User Pause/takeover is permanent. Handoff seals only this actor under original resources; computer_stop does not save/exit. '
        'No source search, hidden game state, saves, shell or OS tools are available. '
        f'Current mechanical session={client.config["session"]}; actor={client.config["actor_id"]}; these audit IDs grant no authority.'),
        on_list_tools=list_tools,on_call_tool=call_tool,
        get_tool_input_schema=lambda name:specs[name][1] if name in specs else None)
    server.middleware.clear()
    return server


async def run(config: Path) -> None:
    client=PlayerClient(config)
    def stop(signum,frame):
        client.stop('MCP signal cancellation')
        raise KeyboardInterrupt
    for sig in (signal.SIGINT,signal.SIGTERM):
        signal.signal(sig,stop)
    try:
        server=make_server(client)
        async with stdio_server() as (read,write):
            await server.run(read,write,server.create_initialization_options())
    finally:
        client.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actor-config',type=Path,required=True)
    anyio.run(run,parser.parse_args().actor_config)
