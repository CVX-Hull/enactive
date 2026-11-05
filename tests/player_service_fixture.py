"""Current real HTTP/MCP composition over a receiver double; no game or API.

Used by the player-host adapter's synthetic provider tests. It cannot qualify native delivery,
actor succession across a live game, or gameplay outcomes.
"""
from pathlib import Path
import sys
import argparse
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import json
import tempfile
import time
import anyio

from harness.application import Application
from harness.computer.runtime import ComputerRuntime
from harness.player.memory import Memory
from harness.player_mcp import run
from harness.server import serve
from tests.test_computer_runtime import Channel, Process


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stdio',action='store_true',required=True)
    parser.add_argument('--actor-id')
    args=parser.parse_args()
    if args.actor_id is not None and (len(args.actor_id)!=32 or any(c not in '0123456789abcdef' for c in args.actor_id)):
        raise SystemExit('Fixture actor identity must be32 lowercase hexadecimal characters')
    with tempfile.TemporaryDirectory(prefix='enactive-player-fixture-') as temporary:
        directory=Path(temporary)
        channel=Channel()
        runtime=ComputerRuntime(directory,'a'*32,channel,Process(),time.monotonic()+90,
            dict(max_inputs=100,max_requests=200,max_frames=200,max_bytes=2**30))
        memory=Memory(directory/'player.sqlite3')
        application=Application(runtime,memory,directory/'contexts')
        server,thread=serve(application,0)
        if args.actor_id is None:
            actor=runtime.add_actor()
        else:
            # Controlled synthetic actor identity lets the real host invocation
            # bind to the actual HTTP/MCP fixture before its subprocess starts.
            # Only minting is deterministic; authorization/context/closure are real.
            with patch('harness.computer.runtime.uuid.uuid4',return_value=SimpleNamespace(hex=args.actor_id)):
                actor=runtime.add_actor()
        config=directory/'actor.json'
        config.write_text(json.dumps(dict(schema='player-adapter/1',base_url=f'http://127.0.0.1:{server.server_port}',
            session=runtime.session,**actor)))
        config.chmod(0o600)
        try:
            anyio.run(run,config)
        finally:
            server.shutdown();server.server_close();thread.join(2)
            runtime.close();memory.close()


if __name__ == '__main__':
    main()
