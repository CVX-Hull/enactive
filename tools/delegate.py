#!/usr/bin/env python3
"""Start the one delegate the lead names, with a brief and a worktree, and return its hand-back.

The lead chooses the coding agent, model, effort and role; this starts exactly that and reports what happened.
It holds no preference: every argument that selects a delegate is required, nothing has a default, and a run
that does not start, returns nothing or is refused is reported as that and never tried on another delegate.
How each coding agent is started and how it reports are data in `.agents/delegates.json`.
This file knows none of them by name.

Runs on the standard library, so a lead on any coding agent can start it with the main checkout's Python.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DELEGATES = ROOT / ".agents/delegates.json"
SCHEMA = "delegates/4"
TOKEN_NAMES = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens")
# The hand-back's own statement of the acceptance check, asked for in the brief when the lead names a check.
REPORTED = re.compile(r"^Acceptance check: (passed|failed|not run)\s*$", re.MULTILINE)
REPORT_LINE = ("End your hand-back with one line of exactly this form, saying what you saw when you ran the "
               "acceptance check: `Acceptance check: passed`, `Acceptance check: failed` or `Acceptance check: not run`.")
# Seconds a stopped delegate gets to end by itself, and seconds for the version line.
GRACE, VERSION_WAIT = 10, 30
EXIT_HANDED_BACK, EXIT_NOT_HANDED_BACK, EXIT_USAGE = 0, 1, 2


def read_delegates(path: Path) -> dict:
    definitions = json.loads(path.read_text(encoding="utf-8"))
    if definitions.get("schema") != SCHEMA:
        raise SystemExit(f"{path}: expected schema {SCHEMA}, found {definitions.get('schema')!r}")
    return definitions


def fill(template: list[str], values: dict[str, str]) -> list[str]:
    """Replace `{name}` placeholders; a brace that names no placeholder is left as written."""
    return [re.sub(r"\{(\w+)\}", lambda match: values.get(match.group(1), match.group(0)), part) for part in template]


def git(worktree: Path, *arguments: str) -> str | None:
    """A git command's output as written, or None when git refuses (the directory is not a repository)."""
    done = subprocess.run(["git", "-C", str(worktree), *arguments], capture_output=True)
    return os.fsdecode(done.stdout) if done.returncode == 0 else None


def uncommitted(worktree: Path) -> dict[str, str] | None:
    """Porcelain status by changed path, including both paths of a rename."""
    status = git(worktree, "status", "--porcelain", "-z", "--untracked-files=all")
    if status is None:
        return None
    records, paths = iter(status.rstrip("\0").split("\0")), {}
    for record in filter(None, records):
        code = record[:2]
        paths[record[3:]] = code
        if "R" in code or "C" in code:
            source = next(records)
            if "R" in code:
                paths[source] = code
    return paths


def content_digest(worktree: Path, name: str) -> tuple[str, str | None]:
    path = worktree / name
    try:
        if any((worktree / parent).is_symlink() for parent in Path(name).parents if parent != Path(".")):
            return "missing", None
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            return "symlink", hashlib.sha256(os.fsencode(os.readlink(path))).hexdigest()
        if stat.S_ISREG(mode):
            with path.open("rb") as contents:
                return "file", hashlib.file_digest(contents, "sha256").hexdigest()
        return ("directory" if stat.S_ISDIR(mode) else "special"), None
    except (FileNotFoundError, NotADirectoryError):
        return "missing", None
    except OSError:
        return "unreadable", None


def staged_blobs(worktree: Path) -> dict[str, str]:
    """Map tracked paths to their Git index mode and blob SHA."""
    raw = git(worktree, "ls-files", "--stage", "-z")
    if not raw:
        return {}
    entries = {}
    for record in filter(None, raw.split("\0")):
        meta, _, name = record.partition("\t")
        if name:
            entries[name] = meta
    return entries


def snapshot(worktree: Path) -> tuple[str, Path, dict[str, tuple[str, str | None, tuple[str, str | None]]]] | None:
    top = (git(worktree, "rev-parse", "--show-toplevel") or "").strip()
    statuses = uncommitted(worktree)
    if not top or statuses is None:
        return None
    repo_root = Path(top).resolve()
    head = (git(worktree, "rev-parse", "--verify", "HEAD") or "").strip()
    staged = staged_blobs(repo_root)
    return head, repo_root, {name: (code, staged.get(name), content_digest(repo_root, name))
                             for name, code in statuses.items()}


def normalize_owned_paths(owned_paths: list[str], worktree: Path, repo_root: Path) -> list[str]:
    rel_worktree = worktree.resolve().relative_to(repo_root)
    base = PurePosixPath() if rel_worktree == Path(".") else PurePosixPath(rel_worktree.as_posix())
    prefixes = []
    for raw in owned_paths:
        if not raw or not raw.strip():
            raise ValueError("--owned-paths entries must be non-empty relative paths")
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"--owned-paths entry must stay inside the worktree: {raw!r}")
        combined = base if path == PurePosixPath(".") else base / path
        prefixes.append(combined.as_posix().rstrip("/"))
    return prefixes


def stop(process: subprocess.Popen) -> None:
    """End the delegate's whole process group: ask, wait, then kill whatever is left, whether or not the
    delegate itself has gone. A child that ignores the request or holds a pipe open does not outlive this."""
    for sign in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sign)
        except ProcessLookupError:
            return
        if sign == signal.SIGTERM:
            try:
                process.wait(timeout=GRACE)
            except subprocess.TimeoutExpired:
                pass


def run(argv: list[str], *, cwd: Path, environment: dict, stdin: str | None, timeout: float | None):
    """Run to the end or to the time limit. Returns (exit code or None when it timed out, stdout, stderr)."""
    process = subprocess.Popen(argv, cwd=cwd, env=environment, text=True, errors="replace", start_new_session=True,
                               stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = process.communicate(stdin, timeout=timeout)
        return process.returncode, out, err
    except subprocess.TimeoutExpired:
        stop(process)
        try:
            out, err = process.communicate(timeout=GRACE)
        except subprocess.TimeoutExpired:  # something outside the group still holds a pipe; stop reading
            out, err = "", "output not collected: a pipe stayed open after the delegate was stopped"
        return None, out, err


def refusal(patterns: list[str], out: str, err: str) -> str | None:
    """The line of a run's output that says the coding agent refused it (quota, sign-in), or None.

    Asked only of a run that failed or returned nothing. A successful hand-back can discuss quotas."""
    for text in (err, out):
        for line in text.splitlines():
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns):
                return line.strip()[:300]
    return None


def json_object(text: str) -> dict:
    """Read an output record, treating malformed or non-object output as absent."""
    try:
        value = json.loads(text)
    except (ValueError, RecursionError):
        return {}
    return value if isinstance(value, dict) else {}


def at_path(record: dict, path: str) -> object:
    value: object = record
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def structured_outcome(record: dict, checks: dict) -> tuple[str | None, str | None]:
    """Classify unsuccessful completion reported in an exit-zero output record."""
    for path in checks.get("timeout_fields", []):
        value = at_path(record, path)
        if isinstance(value, str) and any(re.search(pattern, value, re.IGNORECASE)
                                          for pattern in checks.get("timeout_patterns", [])):
            return "timed_out", f"{path}={value!r}"
    if (path := checks.get("error_flag")) and at_path(record, path) is True:
        return "failed", f"{path}=True"
    if status := checks.get("ok_status"):
        path = status["path"]
        value = at_path(record, path)
        if isinstance(value, str) and value and value.lower() not in {ok.lower() for ok in status["values"]}:
            return "failed", f"{path}={value!r}"
    return None, None


def words(stdout: str) -> str:
    """What the output says: each line as written, or, for a line that is a JSON record, its text values at
    every depth. A count or a timing that happens to be 429 is not a refusal, so numbers and keys are left out."""
    def texts(value: object):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for inner in value.values():
                yield from texts(inner)
        elif isinstance(value, list):
            for inner in value:
                yield from texts(inner)

    said = []
    for line in stdout.splitlines():
        try:
            record = json.loads(line)
        except (ValueError, RecursionError):
            said.append(line)
            continue
        said.extend(text for part in texts(record) for text in part.splitlines())
    return "\n".join(said)


def reported_usage(stdout: str, stdout_object: dict, how: dict) -> tuple[dict[str, int | None] | None, list[str] | None]:
    """Sum reported counts and collect served models from the matching output records."""
    records = (stdout_object,)
    if how["read"] == "stdout_jsonl":
        where = how["where"]
        records = (record for record in map(json_object, stdout.split("\n"))
                   if all(key in record and record[key] == value for key, value in where.items()))

    totals: dict[str, int | None] = dict.fromkeys(TOKEN_NAMES)
    models: set[str] | None = None
    models_path = how.get("models")
    for record in records:
        for name in TOKEN_NAMES:
            count = at_path(record, how["tokens"][name]) if name in how["tokens"] else None
            if type(count) is int and count >= 0:
                totals[name] = (totals[name] or 0) + count
        if models_path is not None:
            reported = at_path(record, models_path)
            if isinstance(reported, dict):
                if models is None:
                    models = set()
                models.update(reported)
    return (totals if any(count is not None for count in totals.values()) else None,
            sorted(models) if models is not None else None)


def write_reports(out: Path, result: dict, head_before: str, check: str | None) -> dict:
    """Save the result and the lead's draft ledger row when a run directory exists."""
    if out.is_dir():
        rerun = (result["check"] or {}).get("rerun")
        row = {
            "schema": "coding-agent-attempt/3",
            "issue": None,
            "kind_of_work": None,
            "base_commit": head_before if re.fullmatch(r"[0-9a-f]{40}", head_before) else None,
            "role": result["role"],
            "coding_agent": result["coding_agent"],
            "coding_agent_version": result["coding_agent_version"],
            "model": result["model"],
            "effort": result["effort"],
            "reason": None,
            "date": result["date"],
            "hand_back": "failed" if result["outcome"] == "unexpected_edits" else result["outcome"],
            "acceptance": rerun if result["role"] == "worker" and rerun in ("passed", "failed") else None,
            "repairs": 0,
            "wall_seconds": result["wall_seconds"],
            "blind_preference": None,
            "outcome": None,
            "findings": {"confirmed": 0, "rejected": 0} if result["role"] == "reviewer" else None,
            "false_report": None,
            "usage": result["usage"],
            "brief_design": None,
            "brief_extent": None,
            "brief_check": True if check else None,
        }
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        (out / "attempt-row-draft.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    return result


def start(definitions: dict, *, coding_agent: str, model: str, effort: str, role: str, brief: str,
          worktree: Path, out: Path, check: str | None, timeout: float | None,
          owned_paths: list[str] | None = None) -> dict:
    """Start the named delegate once and describe what happened. Never starts a different one."""
    result = {"coding_agent": coding_agent, "coding_agent_version": None, "model": model, "effort": effort,
              "role": role, "worktree": str(worktree), "date": date.today().isoformat(), "outcome": None,
              "detail": None, "exit_code": None, "wall_seconds": 0, "hand_back": None, "commits": None,
              "uncommitted": None, "changed_paths": None, "unexpected_edits": None, "check": None,
              "usage": None, "models_reported": None}
    agent = definitions["coding_agents"].get(coding_agent)
    if agent is None:
        raise SystemExit(f"No coding agent {coding_agent!r} in the delegate definitions; "
                         f"known: {', '.join(sorted(definitions['coding_agents']))}")
    how = agent["roles"].get(role)
    if how is None:
        raise SystemExit(f"{agent['name']} has no role {role!r}; known: {', '.join(sorted(agent['roles']))}")
    result["coding_agent"] = agent["name"]
    before = snapshot(worktree)
    head_before = before[0] if before is not None else ""
    if "unavailable" in how:
        result |= {"outcome": "unavailable", "detail": how["unavailable"]}
        return write_reports(out, result, head_before, check)

    out.mkdir(parents=True, exist_ok=True)
    reply_file = out / "reply.md"
    reply_file.unlink(missing_ok=True)
    sent = definitions["role_instruction"].replace("{role}", role) + "\n\n" + brief.strip() + "\n"
    if check:
        sent += "\n" + REPORT_LINE + "\n"
    (out / "brief.txt").write_text(sent, encoding="utf-8")
    environment = {name: value for name, value in os.environ.items() if name not in definitions["drop_environment"]}
    values = {"worktree": str(worktree), "model": model, "effort": effort, "reply_file": str(reply_file), "brief": sent}
    argv = fill(how["argv"], values)

    if shutil.which(argv[0], path=environment.get("PATH")) is None:
        result |= {"outcome": "failed_start", "detail": f"{argv[0]} is not on the path"}
        return write_reports(out, result, head_before, check)
    try:  # The version is a detail of the report; failing to read it does not stop the start.
        version = subprocess.run(agent["version"], capture_output=True, text=True, errors="replace", env=environment,
                                 timeout=VERSION_WAIT).stdout
        result["coding_agent_version"] = (version.strip().splitlines() or [None])[0]
    except (OSError, subprocess.TimeoutExpired):
        pass
    began = time.monotonic()
    try:
        exit_code, stdout, stderr = run(argv, cwd=worktree, environment=environment, timeout=timeout,
                                        stdin=sent if how["brief"] == "stdin" else None)
    except OSError as error:
        result |= {"outcome": "failed_start", "detail": str(error)}
        return write_reports(out, result, head_before, check)
    result["wall_seconds"] = round(time.monotonic() - began)
    after = snapshot(worktree)
    result["exit_code"] = exit_code
    (out / "stdout.txt").write_text(stdout, encoding="utf-8")
    (out / "stderr.txt").write_text(stderr, encoding="utf-8")
    reply_format, usage_format = how["reply"], agent["usage"]
    stdout_object = json_object(stdout) if reply_format != "file" or usage_format["read"] == "stdout_json" else {}
    if reply_format == "file":
        reply = reply_file.read_text(encoding="utf-8", errors="replace") if reply_file.is_file() else ""
    else:
        value = stdout_object.get(reply_format["stdout_json"])
        reply = value if isinstance(value, str) else ""
        reply_file.write_text(reply, encoding="utf-8", errors="replace")
    result["usage"], result["models_reported"] = reported_usage(stdout, stdout_object, usage_format)

    structured, detail = (None, None)
    if exit_code == 0 and reply_format != "file":
        structured, detail = structured_outcome(stdout_object, agent.get("outcome_checks", {}))
    no_hand_back = exit_code != 0 or structured == "failed" or not reply.strip()
    said = words(stdout)
    refused = refusal(agent["refusals"], said, stderr) if no_hand_back and structured != "timed_out" else None
    last_line = (stderr.strip().splitlines() or said.strip().splitlines() or ["no output"])[-1][:300]
    if exit_code == 0 and reply_format != "file" and stdout.strip() and not isinstance(stdout_object.get(reply_format["stdout_json"]), str):
        last_line = (f"stdout is not one JSON object with a text `{reply_format['stdout_json']}`, so the reply was not "
                     f"read (see stdout.txt): {last_line}")[:300]
    if exit_code is None:
        result |= {"outcome": "timed_out", "detail": f"no hand-back within {timeout:g} seconds"}
    elif structured == "timed_out":
        result |= {"outcome": "timed_out", "detail": f"exit code 0 reported a timeout: {detail}"}
    elif refused:
        result |= {"outcome": "refused", "detail": refused}
    elif exit_code != 0:
        result |= {"outcome": "failed", "detail": f"exit code {exit_code}: {last_line}"}
    elif structured == "failed":
        result |= {"outcome": "failed", "detail": f"exit code 0 reported {detail}: {last_line}"}
    elif not reply.strip():
        result |= {"outcome": "empty_reply", "detail": f"exit code 0 and no reply, which is a failed run: {last_line}"}
    else:
        result |= {"outcome": "handed_back", "hand_back": str(reply_file)}

    if before is not None and after is None:
        result["unexpected_edits"] = {"commits": [], "paths": ["<worktree no longer a git repository>"]}
    elif before is not None and after is not None:
        head_after, repo_root, dirty_after = after
        dirty_before = before[2]
        changed = {path for path in dirty_before.keys() | dirty_after.keys()
                   if dirty_before.get(path) != dirty_after.get(path)}
        commits = []
        if head_after and head_after != head_before:
            revision = f"{head_before}..{head_after}" if head_before else head_after
            commits = (git(repo_root, "rev-list", revision) or "").split()
            for commit in commits:
                touched = git(repo_root, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z",
                              "--no-renames", "--root", commit)
                changed.update(filter(None, (touched or "").split("\0")))
            if not commits and head_before:
                diff = git(repo_root, "diff", "--no-renames", "--name-only", "-z", revision, "--")
                changed.update(filter(None, (diff or "").split("\0")))
        changed_paths = sorted(changed)
        result |= {"commits": commits, "uncommitted": list(dirty_after), "changed_paths": changed_paths}
        if how.get("read_only") is True and (head_after != head_before or commits or changed_paths):
            unexpected_commits = commits or ([f"HEAD->{head_after or 'unborn'}"] if head_after != head_before else [])
            result["unexpected_edits"] = {"commits": unexpected_commits, "paths": changed_paths}
        elif not how.get("read_only") and owned_paths:
            prefixes = normalize_owned_paths(owned_paths, worktree, repo_root)
            outside = [path for path in changed_paths
                       if not any(prefix == "." or path == prefix or path.startswith(prefix + "/") for prefix in prefixes)]
            if outside:
                result["unexpected_edits"] = {"commits": [], "paths": outside}
    if (edits := result["unexpected_edits"]) is not None:
        details = [f"{kind}: {', '.join(values)}" for kind, values in edits.items() if values]
        summary = "; ".join(details)
        if result["outcome"] == "handed_back":
            result |= {"outcome": "unexpected_edits", "hand_back": None, "detail": "Unexpected " + summary}
        else:
            result["detail"] = f"{result['detail']}; unexpected {summary}" if result["detail"] else "Unexpected " + summary
    if check:
        # Run again here, outside any sandbox the delegate had, whatever it reported: a delegate that could not
        # run the check, or returned nothing after editing, still leaves a tree the lead needs a result for.
        reported = REPORTED.findall(reply)
        result["check"] = {"command": check, "delegate_reported": reported[-1] if reported else "not stated",
                           "rerun": "not run", "rerun_exit_code": None, "rerun_output": str(out / "check.txt")}
        # What the delegate did is on disk before the rerun starts, so a slow check delays nothing already known.
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        rerun_code, rerun_out, rerun_err = run(["sh", "-c", check], cwd=worktree, environment=environment,
                                               stdin=None, timeout=timeout)
        (out / "check.txt").write_text(rerun_out + rerun_err, encoding="utf-8")
        result["check"] |= {"rerun": "timed_out" if rerun_code is None else "passed" if rerun_code == 0 else "failed",
                            "rerun_exit_code": rerun_code}
    return write_reports(out, result, head_before, check)


def listing(definitions: dict) -> str:
    lines = []
    for key, agent in sorted(definitions["coding_agents"].items()):
        for role, how in sorted(agent["roles"].items()):
            state = "unavailable: " + how["unavailable"] if "unavailable" in how else " ".join(how["argv"][:2]) + " …"
            lines.append(f"{key}\t{role}\t{state}")
    return "\n".join(lines)


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--delegates", type=Path, default=DELEGATES, help="the delegate definitions (default: this checkout's)")
    parser.add_argument("--list", action="store_true", help="list every coding agent and role that can be named, and stop")
    parser.add_argument("--coding-agent", help="the coding agent to start, by its key in the delegate definitions")
    parser.add_argument("--model", help="the model, as that coding agent names it")
    parser.add_argument("--effort", help="the effort, as that coding agent names it")
    parser.add_argument("--role", help="worker, reviewer, explorer or locator")
    parser.add_argument("--brief", help="a file holding the brief, or - for standard input")
    parser.add_argument("--worktree", type=Path, help="the worktree the delegate works in")
    parser.add_argument("--out", type=Path, help="a scratch directory outside the checkout for the reply and the run's output")
    parser.add_argument("--owned-paths", nargs="+", help="worktree-relative files or directories the worker may edit")
    parser.add_argument("--check", help="the brief's acceptance check, run again here in the worktree after the hand-back")
    parser.add_argument("--timeout", type=float, help="seconds to wait for the hand-back; no limit when omitted")
    options = parser.parse_args(arguments)
    definitions = read_delegates(options.delegates)
    if options.list:
        print(listing(definitions))
        return EXIT_HANDED_BACK
    missing = [name for name in ("coding_agent", "model", "effort", "role", "brief", "worktree", "out")
               if getattr(options, name) is None]
    if missing:
        parser.error("the lead names each of these; none has a default: " + ", ".join("--" + name.replace("_", "-") for name in missing))
    if not options.worktree.is_dir():
        parser.error(f"--worktree {options.worktree} is not a directory")
    brief = sys.stdin.read() if options.brief == "-" else Path(options.brief).read_text(encoding="utf-8")
    if not brief.strip():
        parser.error("the brief is empty")
    if options.owned_paths:
        for raw in options.owned_paths:
            path = PurePosixPath(raw)
            if not raw or not raw.strip() or path.is_absolute() or ".." in path.parts:
                parser.error(f"--owned-paths entry must be a non-empty relative path inside the worktree: {raw!r}")
    result = start(definitions, coding_agent=options.coding_agent, model=options.model, effort=options.effort,
                   role=options.role, brief=brief, worktree=options.worktree.resolve(), out=options.out.resolve(),
                   check=options.check, timeout=options.timeout, owned_paths=options.owned_paths)
    print(json.dumps(result, indent=2))
    if result["outcome"] == "handed_back":
        print("\n--- hand-back ---\n" + Path(result["hand_back"]).read_text(encoding="utf-8").rstrip())
        return EXIT_HANDED_BACK
    print(f"\nNo hand-back: {result['outcome']}: {result['detail']}. Nothing else was started; the lead decides what to try next.")
    return EXIT_NOT_HANDED_BACK


if __name__ == "__main__":
    raise SystemExit(main())
