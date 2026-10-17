"""CLI client; only `serve` touches the native request transport."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

from .controller import Controller, ControlError, MAX_WAIT, read_json
from .server import Server

ROOT = Path(__file__).resolve().parent.parent


def expectation(value: str) -> tuple[str, int]:
    try:
        session, revision = value.rsplit(":", 1)
        number = int(revision)
        if not session or number < 0:
            raise ValueError
        return session, number
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use SESSION:REV from observe or status") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Control the real local CDDA game through its serialized service")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Start loopback service; startup always pauses")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--timeout", type=float, default=5.0, help="Native request deadline, 0–15 seconds")
    for name in ("observe", "pause", "resume", "status", "key", "action", "walk", "goal"):
        command = commands.add_parser(name)
        if name in {"key", "action"}:
            command.add_argument(name)
        if name == "goal":
            command.add_argument("text", help="Record planner objective; does not start an autonomous model")
        if name == "walk":
            command.add_argument("direction", choices=("north", "south", "east", "west"))
            command.add_argument("--steps", type=int, required=True)
        if name in {"key", "action", "walk"}:
            command.add_argument("--expect", type=expectation, required=True,
                                 help="Required session:revision from the observation informing this decision")
        if name not in {"status", "goal", "pause"}:
            command.add_argument("--timeout", type=float, default=5.0)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if command == "serve":
        controller = None
        server = None
        try:
            controller = Controller(ROOT, timeout=args["timeout"])
            server = Server(controller, args["port"])
            print(f"CDDA spectator: http://127.0.0.1:{server.port} (paused; observe then resume)", flush=True)
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            return 0
        except (OSError, ControlError) as exc:
            print(f"Service error: {exc}", file=sys.stderr)
            return 1
        finally:
            if server is not None:
                server.server_close()
            if controller is not None:
                controller.close()
        return 0
    try:
        config = read_json(ROOT / ".runtime" / "bridge" / "controller.json")
        if config is not None and (type(config.get("protocol")) is not int or config["protocol"] != 3):
            raise ControlError("Unsupported service protocol; restart a matching native-v3 controller")
        if config is None or type(config.get("port")) is not int or not 1 <= config["port"] <= 65535 or not isinstance(config.get("token"), str):
            raise ControlError("Service configuration missing; run python3 -m harness serve")
        base = f'http://127.0.0.1:{config["port"]}'
        headers = {"Content-Type": "application/json", "X-CDDA-Token": config["token"]}
        if command == "status":
            request = Request(base + "/api/status", headers=headers)
        else:
            if "expect" in args:
                args["expected_session"], args["expected_revision"] = args.pop("expect")
            if "timeout" in args and not 0 < args["timeout"] <= MAX_WAIT:
                raise ControlError("Timeout must be greater than 0 and at most 15 seconds")
            data = json.dumps({"kind": command, **args}).encode()
            request = Request(base + "/api/command", data=data, headers=headers, method="POST")
        # A walk may consume two bounded native exchanges per step; pause remains independent.
        network_timeout = 2 * args.get("timeout", 5) * args.get("steps", 1) + 5
        opener = build_opener(ProxyHandler({}))
        try:
            with opener.open(request, timeout=network_timeout) as response:
                result = json.load(response)
        except HTTPError as exc:
            result = json.load(exc)
            print(json.dumps(result, indent=2))
            return 1
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, URLError, ValueError, ControlError) as exc:
        print(f"Controller error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
