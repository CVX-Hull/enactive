"""Prepare only this trusted checkout's Codex MCP table; never global settings."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import tomllib

from harness.player_tools import tool_specs

ROOT = Path(__file__).resolve().parents[1]
SERVER = "enactive_player"


def configuration(root: Path) -> dict:
    return dict(command=str(root / ".venv" / "bin" / "python"),
        args=["-m", "harness.player_mcp"], cwd=str(root),
        enabled=True, enabled_tools=[spec.name for spec in tool_specs()],
        default_tools_approval_mode="approve", startup_timeout_sec=10,
        tool_timeout_sec=60,
        tools={"enactive_context": {"output_token_limit": 131072}})


def configure(root: Path, *, write=False) -> dict:
    root = root.resolve()
    directory, path = root / ".codex", root / ".codex" / "config.toml"
    if directory.is_symlink() or path.is_symlink():
        raise ValueError("Project Codex configuration must not be a symlink")
    if path.exists() and (not path.is_file() or path.stat().st_size > 1_048_576):
        raise ValueError("Project Codex configuration must be a bounded regular file")
    before = path.read_bytes() if path.exists() else b""
    parsed = tomllib.loads(before.decode())
    expected = configuration(root)
    current = parsed.get("mcp_servers", {}).get(SERVER)
    if current is not None:
        if current != expected:
            raise ValueError("Existing Enactive MCP table differs; review it explicitly before changing setup")
        return dict(path=str(path), changed=False, matches=True, active_host_verified=False)
    if not write:
        return dict(path=str(path), changed=False, matches=False, proposed=expected, active_host_verified=False)
    lines = [f"\n[mcp_servers.{SERVER}]\n"]
    for key, value in expected.items():
        if key != "tools":
            lines.append(key + " = " + json.dumps(value, ensure_ascii=False) + "\n")
    lines.extend([f"\n[mcp_servers.{SERVER}.tools.enactive_context]\n", "output_token_limit = 131072\n"])
    value = before + "".join(lines).encode()
    # Confirm TOML structure, including exact preservation of unrelated settings.
    after = tomllib.loads(value.decode())
    actual = after["mcp_servers"].pop(SERVER)
    if not after["mcp_servers"] and "mcp_servers" not in parsed:
        after.pop("mcp_servers")
    if actual != expected or after != parsed:
        raise ValueError("Proposed project configuration changes unrelated settings")
    directory.mkdir(exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".config-", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        if (path.read_bytes() if path.exists() else b"") != before:
            raise ValueError("Project configuration changed during setup")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return dict(path=str(path), changed=True, matches=True, active_host_verified=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Add only the reviewed project MCP table")
    args = parser.parse_args()
    print(json.dumps(configure(ROOT, write=args.write), indent=2))


if __name__ == "__main__":
    main()
