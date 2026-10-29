"""Describe current tools or write an explicit per-actor Pi MCP configuration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if __package__ in (None,''):
    sys.path.insert(0,str(ROOT))
from harness.player_tools import tool_specs


def configuration(actor_config: str, root: Path = ROOT) -> dict:
    return dict(command=str(root/'.venv/bin/python'),args=['-m','harness.player_mcp','--actor-config',actor_config],
        cwd=str(root),enabled=True,required=True,enabled_tools=list(tool_specs()),
        startup_timeout_sec=15,tool_timeout_sec=30)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--describe',action='store_true')
    parser.add_argument('--template',action='store_true',help='Write the frozen @ACTOR_CONFIG@ MCP template')
    parser.add_argument('--actor-config',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.describe:
        if args.actor_config or args.output or args.template:parser.error('--describe takes no output/actor/template')
        print(json.dumps([dict(name=n,description=d,input_schema=s) for n,(d,s) in tool_specs().items()],indent=2))
        return
    if args.output is None or (args.actor_config is None and not args.template) or (args.actor_config and args.template):
        parser.error('Select fresh --output and either --actor-config or --template')
    actor=None if args.template else args.actor_config.resolve(strict=True)
    output=args.output.resolve()
    if (actor is not None and not actor.is_relative_to(ROOT)) or not output.is_relative_to(ROOT):
        parser.error('Generated current configurations must stay project-local')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:json.dump(configuration('@ACTOR_CONFIG@' if args.template else str(actor)),stream,indent=2);stream.write('\n')


if __name__=='__main__':main()
