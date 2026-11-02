"""Describe current tools or write an explicit per-actor player MCP configuration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if __package__ in (None,''):
    sys.path.insert(0,str(ROOT))
from harness.player_tools import HOST_TOOLS, PROFILES, tool_specs

SERVER='enactive_player'
# Coding-agent configuration shapes, named by file format rather than product.
# The coding-agent host setup page maps each supported host to its format and path.
FORMATS=('mcp-servers-json','mcp-servers-toml')


def configuration(actor_config: str, root: Path = ROOT, *, profile: str) -> dict:
    """One capability class's MCP entry; the custodian enforces the same allowlist plus host-internal tools."""
    return dict(command=str(root/'.venv/bin/python'),args=['-m','harness.player_mcp','--actor-config',actor_config],
        cwd=str(root),enabled=True,required=True,enabled_tools=[t for t in PROFILES[profile] if t not in HOST_TOOLS],
        startup_timeout_sec=15,tool_timeout_sec=30)


def coding_agent_configuration(actor_config: str, form: str, root: Path = ROOT) -> str:
    """One generated lead-side server entry for a flat-profile actor; names and paths derive from source."""
    server=configuration(actor_config,root,profile='flat')
    if form=='mcp-servers-json':
        # This shape has no working-directory field; the module path is explicit instead.
        entry=dict(type='stdio',command=server['command'],args=server['args'],env=dict(PYTHONPATH=server['cwd']))
        return json.dumps(dict(mcpServers={SERVER:entry}),indent=2)+'\n'
    if form=='mcp-servers-toml':
        keys=('command','args','cwd','enabled','enabled_tools','startup_timeout_sec','tool_timeout_sec')
        # JSON scalars and string arrays are valid TOML values.
        return f'[mcp_servers.{SERVER}]\n'+''.join(f'{key} = {json.dumps(server[key])}\n' for key in keys)
    raise ValueError(f'Unsupported coding-agent format: {form}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--describe',action='store_true')
    parser.add_argument('--template',action='store_true',help='Write the frozen @ACTOR_CONFIG@ MCP template')
    parser.add_argument('--coding-agent-format',choices=FORMATS,help='Write a lead-side coding-agent entry for an explicit actor')
    parser.add_argument('--actor-config',type=Path)
    parser.add_argument('--profile',choices=('flat','narrowed'),default='flat',
                        help="The actor's tool profile; must match the package's actor_profile")
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.describe:
        if args.actor_config or args.output or args.template or args.coding_agent_format:
            parser.error('--describe takes no output/actor/template/format')
        print(json.dumps([dict(name=n,description=d,input_schema=s) for n,(d,s) in tool_specs().items()],indent=2))
        return
    if args.output is None or (args.actor_config is None and not args.template) or (args.actor_config and args.template):
        parser.error('Select fresh --output and either --actor-config or --template')
    if args.coding_agent_format and args.template:
        parser.error('A coding-agent entry needs an explicit issued --actor-config')
    actor=None if args.template else args.actor_config.resolve(strict=True)
    output=args.output.resolve()
    if (actor is not None and not actor.is_relative_to(ROOT)) or not output.is_relative_to(ROOT):
        parser.error('Generated current configurations must stay project-local')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:
        if args.coding_agent_format:
            stream.write(coding_agent_configuration(str(actor),args.coding_agent_format))
        else:
            json.dump(configuration('@ACTOR_CONFIG@' if args.template else str(actor),profile=args.profile),stream,indent=2);stream.write('\n')


if __name__=='__main__':main()
