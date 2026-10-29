"""Run the current frozen campaign, inspect status or independently Pause."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_subparsers(dest='command',required=True)
    run=actions.add_parser('run',help='One frozen current campaign through generic Pi')
    run.add_argument('--run',type=Path,required=True)
    for name in ('status','pause'):
        command=actions.add_parser(name)
        command.add_argument('--url',default='http://127.0.0.1:8766')
    args=parser.parse_args(argv)
    if args.command=='run':
        from tools.campaign_run import main as campaign
        return campaign(['--run',str(args.run)])
    url=urlsplit(args.url)
    if url.scheme!='http' or url.hostname!='127.0.0.1' or not url.port or url.username or url.password or url.path or url.query or url.fragment:
        parser.error('Select the exact loopback base URL')
    request=Request(args.url+('/api/status' if args.command=='status' else '/api/pause'),
        data=None if args.command=='status' else b'{}',headers={'Content-Type':'application/json'})
    with urlopen(request,timeout=5) as response:
        print(json.dumps(json.loads(response.read(1048577)),indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
