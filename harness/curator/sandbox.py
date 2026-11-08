"""Default-deny macOS Seatbelt sandbox for curator sessions (ADR 009 isolation; #451).

The boundary: reads only the workspace, the declared tool roots and a fixed set of system paths;
writes only the declared writable directories and the fresh home; no network except one loopback
port (the model proxy); a short Mach-service allowlist (no pasteboard, Launch Services or
keychain); signals and process information for its own processes only. Kernel rlimits cap CPU
time, file size, open files and processes; a supervisor outside the sandbox caps memory, disk
and wall-clock time, because macOS refuses address-space and data limits. Residual risks are
recorded in docs/research-curator-sandbox.md, not hidden here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import resource
import signal
import subprocess
import tempfile
import time

SANDBOX_EXEC = '/usr/bin/sandbox-exec'
# Read-only system roots every macOS process needs to load and run.
SYSTEM_READ = ('/usr', '/bin', '/sbin', '/System', '/Library/Apple', '/private/var/db/dyld',
               '/private/var/db/timezone', '/private/var/select', '/private/etc')
# Devices by name only: never the user's terminals (/dev/ttys*) or disks.
DEVICE_READ = ('/dev/null', '/dev/zero', '/dev/random', '/dev/urandom', '/dev/tty', '/dev/dtracehelper')
# Mach services needed by libc user lookup and logging. Everything else is denied: the
# pasteboard, Launch Services (opening applications), the keychain and window server.
MACH_SERVICES = ('com.apple.system.opendirectoryd.libinfo', 'com.apple.system.notification_center',
                 'com.apple.logd', 'com.apple.system.logger')
# Kernel values a process reads to start (uname, CPU count, page size). Process tables and other
# processes' details are not in the list. The hostname is readable because uname needs it.
SYSCTL_PREFIXES = ('hw.', 'machdep.', 'vm.')
SYSCTL_NAMES = ('kern.osrelease', 'kern.hostname', 'kern.ostype', 'kern.osversion', 'kern.osproductversion',
                'kern.version', 'kern.argmax', 'kern.ngroups', 'kern.maxfilesperproc', 'kern.maxproc',
                'kern.usrstack64', 'kern.secure_kernel', 'kern.osvariant_status', 'kern.boottime',
                'kern.hv_vmm_present', 'sysctl.proc_translated')
DEVICE_WRITE =('/dev/null', '/dev/tty', '/dev/stdout', '/dev/stderr', '/dev/dtracehelper')


class SandboxError(ValueError):
    """The sandbox could not be built as declared."""


@dataclass(frozen=True)
class Limits:
    memory_bytes: int = 2 << 30
    disk_bytes: int = 1 << 30
    file_bytes: int = 64 << 20
    free_space_margin_bytes: int = 1 << 30
    processes: int = 64
    open_files: int = 256
    cpu_seconds: int = 1800
    wall_seconds: float = 1800.
    poll_seconds: float = .1


@dataclass(frozen=True)
class Layout:
    """Absolute, resolved paths. `writable` must lie inside `workspace`; `home` is fresh."""
    workspace: Path
    home: Path
    writable: tuple[Path, ...]
    tools: tuple[Path, ...] = ()
    readable: tuple[Path, ...] = field(default=())

    def __post_init__(self):
        for path in (self.workspace, self.home, *self.writable, *self.tools, *self.readable):
            if not path.is_absolute() or path != path.resolve():
                raise SandboxError(f'Sandbox path must be absolute and resolved: {path}')
            if any(c in str(path) for c in '"\\\n'):
                raise SandboxError(f'Sandbox path has a character the profile cannot quote: {path}')
        for path in self.writable:
            if path == self.workspace or self.workspace not in path.parents:
                raise SandboxError(f'Writable directory must be strictly inside the workspace: {path}')
        if self.home == self.workspace or self.workspace in self.home.parents or self.home in self.workspace.parents:
            raise SandboxError('Home must be a separate directory from the workspace')


def _quote(path: Path | str) -> str:
    return f'"{path}"'


def profile(layout: Layout, proxy_port: int | None) -> str:
    """The SBPL text for one session. Only the proxy port is reachable, and only on loopback."""
    if proxy_port is not None and not (0 < proxy_port < 65536):
        raise SandboxError('Invalid proxy port')
    roots = (*SYSTEM_READ, layout.workspace, layout.home, *layout.tools, *layout.readable)
    read = ' '.join(f'(subpath {_quote(p)})' for p in roots)
    # Metadata only for the readable roots and the directories on the way to them, so path
    # resolution works but nothing else on the disk can be probed for existence or size.
    ancestors = sorted({str(parent) for root in roots for parent in Path(root).parents} | {'/'})
    metadata = ' '.join([read, *(f'(literal {_quote(p)})' for p in ancestors),
                         *(f'(literal {_quote(p)})' for p in DEVICE_READ), '(literal "/dev")'])
    write = ' '.join(f'(subpath {_quote(p)})' for p in (*layout.writable, layout.home))
    devices = ' '.join(f'(literal {_quote(p)})' for p in DEVICE_WRITE)
    device_read = ' '.join(f'(literal {_quote(p)})' for p in DEVICE_READ)
    fds = '(regex #"^/dev/fd/[0-9]+$")'
    mach = ' '.join(f'(global-name {_quote(name)})' for name in MACH_SERVICES)
    sysctl = ' '.join([*(f'(sysctl-name-prefix {_quote(p)})' for p in SYSCTL_PREFIXES),
                       *(f'(sysctl-name {_quote(n)})' for n in SYSCTL_NAMES)])
    lines = [
        '(version 1)',
        '(deny default)',
        '(allow process-exec process-fork)',
        '(allow signal (target self))',
        '(allow process-info* (target self))',
        f'(allow sysctl-read {sysctl})',
        f'(allow mach-lookup {mach})',
        f'(allow file-read-metadata {metadata} {fds})',
        f'(allow file-ioctl {device_read} {fds})',
        f'(allow file-read* (literal "/") {read} {device_read} {fds})',
        f'(allow file-write* {write} {devices} {fds})',
    ]
    if proxy_port is not None:
        lines.append(f'(allow network-outbound (remote ip "localhost:{proxy_port}"))')
    return '\n'.join(lines) + '\n'


def environment(layout: Layout, *, proxy_port: int | None, token: str | None,
                extra: dict[str, str] | None = None) -> dict[str, str]:
    """A minimal environment: nothing inherited, fresh home, temporary files in scratch."""
    path = ':'.join([*(str(p) for p in layout.tools if p.is_dir()), '/usr/bin', '/bin', '/usr/sbin', '/sbin'])
    scratch = next((p for p in layout.writable if p.name == 'scratch'), layout.writable[0])
    env = dict(HOME=str(layout.home), PATH=path, TMPDIR=str(scratch) + '/', LANG='C.UTF-8',
               USER='curator', LOGNAME='curator', SHELL='/bin/sh')
    if proxy_port is not None:
        env['CURATOR_PROXY_URL'] = f'http://127.0.0.1:{proxy_port}'
    if token is not None:
        env['CURATOR_PROXY_TOKEN'] = token
    for key, value in (extra or {}).items():
        if key in env:
            raise SandboxError(f'Extra environment may not replace {key}')
        env[key] = value
    return env


def _user_processes() -> int:
    out = subprocess.run(['/bin/ps', '-U', str(os.getuid()), '-o', 'pid='], capture_output=True, text=True,
                         check=True).stdout
    return len(out.split())


def _limit_child(limits: Limits, nproc: int):
    def apply():
        os.setpriority(os.PRIO_PROCESS, 0, 19)
        resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds))
        resource.setrlimit(resource.RLIMIT_FSIZE, (limits.file_bytes, limits.file_bytes))
        resource.setrlimit(resource.RLIMIT_NOFILE, (limits.open_files, limits.open_files))
        # macOS counts RLIMIT_NPROC per user, so the cap is the user's current count plus the
        # session's allowance; it binds only processes that inherit it.
        resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return apply


def _tree(leader: int) -> dict[int, int]:
    """pid → resident bytes for the leader's process group and descendants."""
    out = subprocess.run(['/bin/ps', '-A', '-o', 'pid=,ppid=,pgid=,rss='], capture_output=True, text=True,
                         check=True).stdout
    rows = [tuple(int(v) for v in line.split()) for line in out.splitlines() if line.strip()]
    members = {pid for pid, _ppid, pgid, _rss in rows if pgid == leader}
    changed = True
    while changed:
        changed = False
        for pid, ppid, _pgid, _rss in rows:
            if ppid in members and pid not in members:
                members.add(pid)
                changed = True
    return {pid: rss * 1024 for pid, _ppid, _pgid, rss in rows if pid in members}


class Unmeasurable(OSError):
    """The writable tree could not be measured; the supervisor treats this as a breach."""


def _disk(paths) -> int:
    """Allocated bytes under the writable roots. Any unreadable directory or entry is a breach,
    so hiding data behind a mode-000 directory or an over-long path stops the session."""
    total = 0

    def fail(error):
        raise Unmeasurable(str(error))

    for root in paths:
        for directory, _dirs, files in os.walk(root, onerror=fail):
            for name in files:
                try:
                    total += os.lstat(os.path.join(directory, name)).st_blocks * 512
                except FileNotFoundError:
                    pass
                except OSError as error:
                    raise Unmeasurable(str(error)) from error
    return total


def _free_bytes(path: Path) -> int:
    stats = os.statvfs(path)
    return stats.f_bavail * stats.f_frsize


@dataclass
class Result:
    returncode: int | None
    stopped: str | None
    peak_memory_bytes: int
    peak_disk_bytes: int
    seconds: float
    survivors: list[int]


def _kill(pids, sig):
    for pid in pids:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass


def run(argv: list[str], layout: Layout, *, proxy_port: int | None = None, token: str | None = None,
        limits: Limits = Limits(), extra_env: dict[str, str] | None = None,
        stdin=subprocess.DEVNULL, stdout=None, stderr=None) -> Result:
    """Run argv inside the sandbox under the supervisor; always closes the whole process tree."""
    for path in (layout.workspace, layout.home, *layout.writable):
        if not path.is_dir():
            raise SandboxError(f'Missing sandbox directory: {path}')
    if any(layout.home.iterdir()):
        raise SandboxError('Home must be empty at session start')
    env = environment(layout, proxy_port=proxy_port, token=token, extra=extra_env)
    nproc = _user_processes() + limits.processes
    with tempfile.NamedTemporaryFile('w', suffix='.sb', delete=False) as handle:
        handle.write(profile(layout, proxy_port))
    floor = _free_bytes(layout.workspace) - limits.disk_bytes - limits.free_space_margin_bytes
    started = time.monotonic()
    peak_memory = peak_disk = 0
    stopped = None
    child = None
    try:
        child = subprocess.Popen([SANDBOX_EXEC, '-f', handle.name, *argv], cwd=layout.workspace, env=env,
                                 stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True,
                                 preexec_fn=_limit_child(limits, nproc), close_fds=True)
        while child.poll() is None:
            try:
                tree = _tree(child.pid)
                memory, disk = sum(tree.values()), _disk((*layout.writable, layout.home))
                free = _free_bytes(layout.workspace)
            except Unmeasurable:
                stopped = 'disk unmeasurable'
                break
            peak_memory, peak_disk = max(peak_memory, memory), max(peak_disk, disk)
            if memory > limits.memory_bytes:
                stopped = 'memory limit'
            elif disk > limits.disk_bytes:
                stopped = 'disk limit'
            elif free < floor:
                # Space used outside the measured tree (unlinked open files, for example) still
                # counts: the volume may not lose more than the session's allowance plus a margin.
                stopped = 'volume free-space floor'
            elif len(tree) > limits.processes:
                stopped = 'process limit'
            elif time.monotonic() - started > limits.wall_seconds:
                stopped = 'wall-clock limit'
            if stopped:
                break
            time.sleep(limits.poll_seconds)
    finally:
        # Any supervisor failure still closes the tree before the error propagates.
        survivors = _close(child) if child is not None else []
        os.unlink(handle.name)
    return Result(child.returncode, stopped, peak_memory, peak_disk, time.monotonic() - started, survivors)


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # macOS refuses signal zero to a group whose only member is an unreaped zombie.
        return any(pid != pgid for pid in _tree(pgid))


def _signal_group(pgid: int, sig) -> None:
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _close(child: subprocess.Popen) -> list[int]:
    """Stop the group and every descendant still attached; report any that remain.

    The tree is read only while the group exists, so a reused process ID is never signalled.
    A descendant that left the group and was orphaned cannot be identified safely; it stays
    confined by the inherited profile and is a recorded residual risk.
    """
    alive = _group_alive(child.pid)
    for sig, seconds in ((signal.SIGTERM, 1.), (signal.SIGKILL, 2.)):
        if not alive:
            break  # once gone, never look again: the ID may be reused
        tree = _tree(child.pid)
        _signal_group(child.pid, sig)
        _kill(tree, sig)
        end = time.monotonic() + seconds
        while time.monotonic() < end and alive:
            child.poll()
            alive = _group_alive(child.pid)
            time.sleep(.02)
    child.wait()
    return sorted(_tree(child.pid)) if alive and _group_alive(child.pid) else []
