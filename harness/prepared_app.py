"""CDDA's prepared launch script and shared project-local installation lock."""
from contextlib import contextmanager
import fcntl
from pathlib import Path
import shlex


def game_lock_path(runtime: Path) -> Path:
    return runtime / 'bridge' / 'game.lock'


@contextmanager
def game_lock(runtime: Path):
    """Exclude owned game sessions while changing their installed app or settings."""
    path=game_lock_path(runtime)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another owner holds the game lock; close the owned game before preparing") from error
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def wrapper_source(root: Path) -> str:
    """Return the fixed script for this canonical checkout; never execute it."""
    runtime = root.resolve() / ".runtime"
    return (
        "#!/bin/sh\nset -eu\n"
        f"cd {shlex.quote(str(runtime / 'Cataclysm.app' / 'Contents' / 'Resources'))}\n"
        "export SDL_MAC_BACKGROUND_APP=1 SDL_WINDOW_NO_ACTIVATION_WHEN_SHOWN=1\n"
        'export DYLD_LIBRARY_PATH="$PWD" DYLD_FRAMEWORK_PATH="$PWD"\n'
        # Protected /bin/sh strips inherited DYLD variables on macOS. The
        # computer launcher supplies and validates this non-DYLD library path.
        'export DYLD_INSERT_LIBRARIES="$ENACTIVE_COMPUTER_LIBRARY"\n'
        f"exec ./cataclysm-tiles --userdir {shlex.quote(str(runtime / 'user') + '/')} "
        f">>{shlex.quote(str(runtime / 'logs' / 'game.log'))} 2>&1\n"
    )
