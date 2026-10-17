"""Install our built binary into the project app and force isolated windowed launch."""
from pathlib import Path
import argparse
import hashlib
import json
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def prepare(binary: Path) -> None:
    app = ROOT / ".runtime" / "Cataclysm.app"
    resources = app / "Contents" / "Resources"
    if not resources.is_dir():
        raise SystemExit("Official project-local app missing; run tools/setup.py first")
    user = ROOT / ".runtime" / "user"
    config = user / "config"
    config.mkdir(parents=True, exist_ok=True)
    options_path = config / "options.json"
    options = json.loads(options_path.read_text()) if options_path.exists() else []
    values = {"FULLSCREEN": "no", "TERMINAL_X": "120", "TERMINAL_Y": "40",
              "TURN_DURATION": "0.0", "USE_LANG": "en"}
    for name, value in values.items():
        existing = next((item for item in options if item["name"] == name), None)
        if existing is None:
            options.append({"name": name, "value": value})
        else:
            existing["value"] = value
    options_path.write_text(json.dumps(options, indent=2) + "\n")
    bridge = ROOT / ".runtime" / "bridge"
    bridge.mkdir(exist_ok=True, mode=0o700)
    bridge.chmod(0o700)
    (bridge / "pause").touch()
    logs = ROOT / ".runtime" / "logs"
    logs.mkdir(exist_ok=True)
    target = resources / "cataclysm-tiles"
    original = resources / "cataclysm-tiles.official"
    if not original.exists():
        shutil.copy2(target, original)
    shutil.copy2(binary, target)
    # Use the official bundled FreeType runtime, not a global Homebrew path.
    dependencies = subprocess.check_output(["otool", "-L", str(target)], text=True)
    for line in dependencies.splitlines()[1:]:
        dependency = line.strip().split(" (", 1)[0]
        if dependency.startswith("/opt/") and dependency.endswith("libfreetype.6.dylib"):
            subprocess.run(["install_name_tool", "-change", dependency,
                            "@executable_path/libfreetype.6.dylib", str(target)], check=True)
    subprocess.run(["codesign", "--force", "--sign", "-", str(target)], check=True)
    wrapper = app / "Contents" / "MacOS" / "Cataclysm.sh"
    wrapper.write_text(
        "#!/bin/sh\nset -eu\n"
        f"cd {shlex.quote(str(resources))}\n"
        f"export CDDA_HARNESS_DIR={shlex.quote(str(bridge))}\n"
        'export DYLD_LIBRARY_PATH="$PWD" DYLD_FRAMEWORK_PATH="$PWD"\n'
        f"exec ./cataclysm-tiles --userdir {shlex.quote(str(user) + '/')} "
        f">>{shlex.quote(str(logs / 'game.log'))} 2>&1\n"
    )
    wrapper.chmod(0o755)
    print(f"Prepared windowed app: {app}")
    print(f"Installed binary SHA256: {hashlib.sha256(target.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    prepare(parser.parse_args().binary.resolve())
