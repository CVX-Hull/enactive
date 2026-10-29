"""Apply only the macOS deployment-target compatibility patch to pinned CDDA."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_TARGET = b"-mmacosx-version-min=10.15"
SUPPORTED_TARGET = b"-mmacosx-version-min=13.0"


def validate_source(source: Path, pin: dict) -> None:
    """Reject semantic builds and source drift without restoring or writing files."""
    legacy = source / ".harness-originals"
    candidates = list((source / "src").rglob("*")) + list(source.rglob("CMakeLists.txt"))
    for path in candidates:
        if path.is_file() and ("cdda_harness" in path.name or
                (path.suffix in {".cpp", ".h", ".hpp", ".cc", ".cxx", ".cmake"}
                 or path.name == "CMakeLists.txt") and b"cdda_harness" in path.read_bytes()):
            legacy = path
            break
    if legacy.exists():
        raise ValueError(f"Legacy semantic source found: {legacy}; preserve it and use a fresh --extract")
    for name, checksum in pin["source_files"].items():
        data = (source / name).read_bytes()
        if name == "Makefile":
            # Repeated builds may reuse exactly our sole compatibility change.
            data = data.replace(SUPPORTED_TARGET, UPSTREAM_TARGET)
        if hashlib.sha256(data).hexdigest() != checksum:
            raise ValueError(f"Upstream source differs from pinned release: {name}; use a fresh --extract")
    make_text = (source / "Makefile").read_bytes()
    if (make_text.count(UPSTREAM_TARGET), make_text.count(SUPPORTED_TARGET)) not in {(2, 0), (0, 2)}:
        raise ValueError("Pinned deployment target anchors changed; use a fresh --extract")


def patch_source(source: Path, pin: dict) -> None:
    validate_source(source, pin)
    makefile = source / "Makefile"
    original = makefile.read_bytes()
    patched = original.replace(UPSTREAM_TARGET, SUPPORTED_TARGET)
    if patched != original:
        makefile.write_bytes(patched)


def main() -> None:
    source = Path(sys.argv[1]).resolve()
    pin = json.loads((ROOT / "native/upstream.json").read_text())
    patch_source(source, pin)
    print(f"Prepared pinned upstream source with macOS compatibility target: {source}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error))
