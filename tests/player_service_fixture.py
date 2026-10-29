"""Current real HTTP/MCP composition over a receiver double; no game or API.

Used by the Pi host's synthetic provider tests. It cannot qualify native delivery,
actor succession across a live game, or gameplay outcomes.
"""
from pathlib import Path
import sys

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
    if sys.argv[1:] != ['--stdio']:
        raise SystemExit('Only the test stdio fixture is supported')
    with tempfile.TemporaryDirectory(prefix='enactive-player-fixture-') as temporary:
        directory=Path(temporary)
        channel=Channel()
        runtime=ComputerRuntime(directory,'a'*32,channel,Process(),time.monotonic()+90,
            dict(max_inputs=100,max_requests=200,max_frames=200,max_bytes=2**30))
        memory=Memory(directory/'player.sqlite3')
        application=Application(runtime,memory,directory/'contexts')
        server,thread=serve(application,0)
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
