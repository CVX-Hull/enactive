"""The one prepared launch script, shared by installation and root validation."""
from pathlib import Path
import shlex


def wrapper_source(root: Path) -> str:
    """Return the fixed script for this canonical checkout; never execute it."""
    runtime = root.resolve() / ".runtime"
    return (
        "#!/bin/sh\nset -eu\n"
        f"cd {shlex.quote(str(runtime / 'Cataclysm.app' / 'Contents' / 'Resources'))}\n"
        f"export CDDA_HARNESS_DIR={shlex.quote(str(runtime / 'bridge'))}\n"
        'export DYLD_LIBRARY_PATH="$PWD" DYLD_FRAMEWORK_PATH="$PWD"\n'
        f"exec ./cataclysm-tiles --userdir {shlex.quote(str(runtime / 'user') + '/')} "
        f">>{shlex.quote(str(runtime / 'logs' / 'game.log'))} 2>&1\n"
    )
