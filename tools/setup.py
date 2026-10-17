#!/usr/bin/env python3
"""Inspect setup, or explicitly download/extract/build the pinned macOS game."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import venv

ROOT = Path(__file__).resolve().parents[1]
FREETYPE_URL = "https://download.savannah.gnu.org/releases/freetype/freetype-2.14.3.tar.xz"
FREETYPE_SHA256 = "36bc4f1cc413335368ee656c42afca65c5a3987e8768cc28cf11ba775e785a5f"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> None:
    if not path.is_file() or sha256(path) != expected:
        raise ValueError(f"Missing or SHA-256 mismatch: {path}; remove corrupt cache and use --download")


def download(url: str, target: Path, expected: str) -> None:
    if target.exists():
        verify(target, expected)
        print(f"Verified cached {target.name}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=target.name + ".", suffix=".part", dir=target.parent)
    os.close(descriptor)
    partial = Path(name)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "CDDA-Player-setup/1"})
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output)
        verify(partial, expected)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    print(f"Downloaded and verified {target.name}")


def extract_archive(archive: Path, destination: Path) -> Path:
    """Validate all paths/links before extraction; never merge with an existing tree."""
    if destination.exists():
        raise ValueError(f"Extraction destination already exists: {destination}")
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        roots = set()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError(f"Unsafe archive path: {member.name}")
            roots.add(path.parts[0])
            if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                raise ValueError(f"Unsupported archive entry: {member.name}")
            if member.issym() or member.islnk():
                link = PurePosixPath(member.linkname)
                base = path.parent if member.issym() else PurePosixPath()
                resolved = (destination / str(base / link)).resolve()
                if link.is_absolute() or not resolved.is_relative_to(destination.resolve()):
                    raise ValueError(f"Unsafe archive link: {member.name}")
        if len(roots) != 1:
            raise ValueError("Expected a single archive root directory")
        destination.mkdir(parents=True)
        try:
            # The data filter also rejects traversal through previously extracted symlinks.
            bundle.extractall(destination, filter="data")
        except BaseException:
            shutil.rmtree(destination)
            raise
    result = destination / roots.pop()
    if not result.is_dir():
        raise ValueError("Archive root is not a directory")
    return result


def write_manifest(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def load_manifest(path: Path, pin: dict) -> dict:
    value = json.loads(path.read_text())
    workspace = Path(value["workspace"])
    if (not workspace.is_absolute() or any(c.isspace() for c in str(workspace))
            or not workspace.name.startswith("cdda-player-build-")):
        raise ValueError("Invalid build workspace in manifest; use a fresh --extract")
    marker = workspace / ".cdda-player-owner"
    if not marker.is_file() or marker.read_text() != str(ROOT):
        raise ValueError("Build workspace ownership differs; use a fresh --extract")
    if value["source_sha256"] != pin["source_sha256"]:
        raise ValueError("Build manifest does not match pinned source; use a fresh --extract")
    if value["freetype_sha256"] != FREETYPE_SHA256:
        raise ValueError("Build manifest does not match pinned FreeType; use a fresh --extract")
    for name in ("source", "freetype"):
        if not Path(value[name]).resolve().is_relative_to(workspace.resolve()):
            raise ValueError(f"Build {name} escapes owned workspace")
    return value


def install_app(image: Path, runtime: Path) -> None:
    target = runtime / "Cataclysm.app"
    if target.exists():
        raise ValueError(f"App already exists: {target}; refusing to replace a possibly running app")
    with tempfile.TemporaryDirectory(prefix="cdda-player-mount-", dir="/tmp") as mount:
        attached = False
        staged = runtime / "Cataclysm.app.partial"
        if staged.exists():
            raise ValueError(f"Remove incomplete app copy before retrying: {staged}")
        try:
            subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", mount,
                            str(image)], check=True)
            attached = True
            apps = list(Path(mount).glob("*.app"))
            if len(apps) != 1:
                raise ValueError("Expected one official app in mounted image")
            subprocess.run(["ditto", str(apps[0]), str(staged)], check=True)
            staged.rename(target)
        finally:
            if attached:
                subprocess.run(["hdiutil", "detach", mount], check=True)
            if staged.exists():
                shutil.rmtree(staged)


def build_command(value: dict, jobs: int) -> list[str]:
    workspace = Path(value["workspace"])
    return ["make", "-C", value["source"], f"-j{jobs}", "NATIVE=osx", "CLANG=1",
            "TILES=1", "SOUND=1", "RELEASE=1", "LOCALIZE=0", "FRAMEWORK=1",
            f"FRAMEWORKSDIR={workspace / 'resources'}",
            f"PKG_CONFIG={workspace / 'pkg-config'}", "OPTLEVEL=-O1",
            "RELEASE_FLAGS=-Wno-error=missing-noreturn", "cataclysm-tiles"]


def prepare_build(value: dict, runtime: Path) -> None:
    workspace = Path(value["workspace"])
    resources = runtime / "Cataclysm.app/Contents/Resources"
    for name in ("SDL2", "SDL2_image", "SDL2_ttf", "SDL2_mixer"):
        if not (resources / f"{name}.framework/Headers").is_dir():
            raise ValueError(f"Missing bundled {name} framework; install official app with --app")
    library = resources / "libfreetype.6.dylib"
    if not library.is_file():
        raise ValueError("Missing bundled FreeType runtime; install official app with --app")
    if not (workspace / "resources").exists():
        (workspace / "resources").symlink_to(resources, target_is_directory=True)
    libdir = workspace / "lib"
    libdir.mkdir(exist_ok=True)
    link = libdir / "libfreetype.dylib"
    if not link.exists():
        link.symlink_to(library)
    include = Path(value["freetype"]) / "include"
    if not (include / "ft2build.h").is_file():
        raise ValueError("Missing local FreeType headers; use a fresh --extract")
    shim = workspace / "pkg-config"
    shim.write_text(
        "#!/usr/bin/env python3\nimport sys\n"
        "flags = {\n"
        f"    ('--cflags', 'freetype2'): '-I{include}',\n"
        f"    ('--libs', 'freetype2'): '-L{libdir} -lfreetype',\n"
        "}\ntry:\n    print(flags[tuple(sys.argv[1:])])\n"
        "except KeyError:\n    sys.exit('Only pinned Makefile FreeType queries are supported')\n"
    )
    shim.chmod(0o755)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, epilog="No flags: read-only setup status. Never launches the game.")
    parser.add_argument("--download", action="store_true", help="download and verify source, app image, FreeType headers")
    parser.add_argument("--extract", action="store_true", help="extract verified source/headers into a new recorded /tmp workspace")
    parser.add_argument("--app", action="store_true", help="copy verified official app image; refuse existing app")
    parser.add_argument("--venv", action="store_true", help="create project .venv using current Python, without packages")
    parser.add_argument("--build", action="store_true", help="patch and compile recorded source; no app replacement")
    parser.add_argument("--install", action="store_true", help="install recorded built binary; quit game first")
    parser.add_argument("--jobs", type=int, default=6, help="native build jobs (default: 6)")
    args = parser.parse_args(argv)
    if args.jobs < 1 or args.jobs > 64:
        parser.error("--jobs must be between 1 and 64")
    pin = json.loads((ROOT / "native/upstream.json").read_text())
    runtime = ROOT / ".runtime"
    downloads = runtime / "downloads"
    manifest = runtime / "build-manifest.json"
    if not any((args.download, args.extract, args.app, args.venv, args.build, args.install)):
        print(f"Pinned CDDA {pin['release']}; Python {platform.python_version()}")
        print(f"Official app: {'present' if (runtime / 'Cataclysm.app').exists() else 'missing'}")
        print(f"Build manifest: {manifest if manifest.exists() else 'missing'}")
        print("Use --help for explicit stages; see docs/setup.md")
        return 0
    archives = [
        (pin["source_url"], downloads / "cdda-0.I-1-source.tar.gz", pin["source_sha256"]),
        (pin["macos_url"], downloads / "cdda-0.I-1.dmg", pin["macos_sha256"]),
        (FREETYPE_URL, downloads / "freetype-2.14.3.tar.xz", FREETYPE_SHA256),
    ]
    if (args.app or args.build or args.install) and platform.system() != "Darwin":
        parser.error("--app, --build and --install require macOS and existing Xcode command-line tools")
    if args.download:
        for url, path, checksum in archives:
            download(url, path, checksum)
    if args.venv:
        target = ROOT / ".venv"
        if target.exists():
            print(f"Keeping existing environment: {target}")
        else:
            venv.EnvBuilder(with_pip=False).create(target)
    if args.extract:
        if manifest.exists():
            raise ValueError(f"Manifest already exists: {manifest}; preserve or remove it before a fresh extraction")
        for _, path, checksum in (archives[0], archives[2]):
            verify(path, checksum)
        workspace = Path(tempfile.mkdtemp(prefix="cdda-player-build-", dir="/tmp")).resolve()
        (workspace / ".cdda-player-owner").write_text(str(ROOT))
        value = {"workspace": str(workspace), "source_sha256": pin["source_sha256"],
                 "freetype_sha256": FREETYPE_SHA256, "state": "extracting"}
        write_manifest(manifest, value)
        source = extract_archive(archives[0][1], workspace / "game")
        freetype = extract_archive(archives[2][1], workspace / "headers")
        value.update(source=str(source), freetype=str(freetype), state="extracted")
        write_manifest(manifest, value)
        print(f"Extracted into recorded workspace: {workspace}")
    if args.app:
        verify(archives[1][1], archives[1][2])
        install_app(archives[1][1], runtime)
    if args.build:
        value = load_manifest(manifest, pin)
        prepare_build(value, runtime)
        subprocess.run([sys.executable, str(ROOT / "tools/patch_game.py"), value["source"]], check=True)
        command = build_command(value, args.jobs)
        value.update(state="building", build_command=command)
        value.pop("binary_sha256", None)
        write_manifest(manifest, value)
        print(shlex.join(command), flush=True)
        subprocess.run(command, check=True)
        binary = Path(value["source"]) / "cataclysm-tiles"
        value.update(state="built", binary_sha256=sha256(binary))
        write_manifest(manifest, value)
    if args.install:
        processes = subprocess.check_output(["ps", "-axo", "comm="], text=True)
        if any(line.strip().endswith("/cataclysm-tiles") or line.strip() == "cataclysm-tiles"
               for line in processes.splitlines()):
            raise ValueError("CDDA is running; quit normally before --install")
        value = load_manifest(manifest, pin)
        if value["state"] != "built":
            raise ValueError("No completed build recorded; run --build first")
        binary = Path(value["source"]) / "cataclysm-tiles"
        verify(binary, value["binary_sha256"])
        subprocess.run([sys.executable, str(ROOT / "tools/prepare_game.py"), str(binary)], check=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, tarfile.TarError, subprocess.CalledProcessError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        raise SystemExit(1)
