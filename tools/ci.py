"""Choose proportionate validation from complete Git comparisons.

A pull request gets the narrowest closed profile its complete diff qualifies for, and full otherwise.
A push to main gets the structural `main` profile: main's ruleset requires the pull request's
`controller` check with strict up-to-date status and squash merges, so main's new tree is the pull
request head that check already tested."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ".github/workflows/check.yml"
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_REGULAR = {"000000", "100644", "100755"}
_ASSETS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".mp4", ".webm"}


class EvidenceUnavailable(ValueError):
    """The requested cheap profile is not established; use full validation."""


@dataclass(frozen=True)
class Change:
    path: str
    before: str
    after: str

    @property
    def regular(self) -> bool:
        return self.before in _REGULAR and self.after in _REGULAR


@dataclass(frozen=True)
class Plan:
    profile: str
    reason: str


# The checker inspects these root documents and every Markdown file in docs/.
ROOT_DOCUMENTS = {"README.md", "AGENTS.md", "NOTICE.md", "CONTRIBUTING.md", "SECURITY.md"}
SMOKE_TESTS = (
    "tests/test_computer_protocol.py",
    "tests/test_computer_runtime.py",
    "tests/test_player_application.py",
    "tests/test_server.py",
)
# Explicit demonstrated boundaries, not inferred dependency-impact analysis.
COMPONENT_PATHS = {
    # Entries ending in "/" cover that whole tree (the spectator page, its modules and vendored libraries).
    "viewer": {"web/", "tests/test_viewer.cjs", "tests/test_investigation.cjs", "tests/test_investigation_session.cjs",
               "tests/fixtures/spectator/"},
}
COMPONENT_TESTS = {
    "viewer": ("tests/test_cli.py", *SMOKE_TESTS),
}


def editorial(path: str) -> bool:
    value = PurePosixPath(path)
    if path in ROOT_DOCUMENTS or path.startswith("docs/") and value.suffix == ".md":
        return True
    if path.startswith("docs/acceptance/") and value.suffix in {".json", *_ASSETS}:
        return True
    return path.startswith("docs/assets/") and value.suffix in _ASSETS


def component(changes: list[Change]) -> str | None:
    if not changes or any(not change.regular for change in changes):
        return None
    paths = {change.path for change in changes if not editorial(change.path)}
    for name, allowed in COMPONENT_PATHS.items():
        covered = lambda path: path in allowed or any(entry.endswith("/") and path.startswith(entry) for entry in allowed)
        if paths and all(covered(path) for path in paths):
            return name
    return None


def _sha(value) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise EvidenceUnavailable("Missing or unsupported Git identity")
    return value


class Repository:
    def __init__(self, root: Path):
        self.root = root

    def command(self, arguments: list[str]) -> bytes:
        return subprocess.run(arguments, cwd=self.root, check=True, capture_output=True,
                              timeout=60).stdout

    def git(self, *arguments: str) -> str:
        return self.command(["git", *arguments]).decode().strip()

    def changes(self, before: str, after: str, *, merge_base: bool = False) -> list[Change]:
        before, after = _sha(before), _sha(after)
        if merge_base:
            before = _sha(self.git("merge-base", before, after))
        raw = self.command(["git", "diff", "--raw", "-z", "--no-renames", before, after, "--"])
        if not raw:
            raise EvidenceUnavailable("Empty comparison requires full validation")
        parts = raw.split(b"\0")
        if parts.pop() != b"" or len(parts) % 2:
            raise EvidenceUnavailable("Incomplete Git comparison")
        result = []
        for header, path in zip(parts[::2], parts[1::2]):
            fields = header.decode().split()
            if len(fields) != 5 or not fields[0].startswith(":") or fields[-1] not in ("A", "D", "M", "T"):
                raise EvidenceUnavailable("Unsupported Git comparison")
            result.append(Change(path.decode(), fields[0][1:], fields[1]))
        return result


def choose(repository: Repository, event_name: str, event: dict, sha: str) -> Plan:
    head = _sha(sha)
    if repository.git("rev-parse", "HEAD") != head:
        # Full checks cannot repair validation of the wrong checkout.
        raise RuntimeError("Checkout differs from the event; refusing validation of another candidate")
    if event_name == "push" and event.get("ref") == "refs/heads/main" and event.get("after") == head:
        return Plan("main", "Main's ruleset merged this tree only after its pull request's controller check "
                            "passed on it, strict and up to date")
    try:
        if event_name != "pull_request":
            raise EvidenceUnavailable("Unsupported event requires full validation")
        pr = event.get("pull_request") or {}
        if pr.get("base", {}).get("ref") != "main":
            raise EvidenceUnavailable("Only main-targeting PRs have reduced validation")
        changes = repository.changes(pr["base"]["sha"], pr["head"]["sha"], merge_base=True)
        if changes and all(change.regular and editorial(change.path) for change in changes):
            return Plan("editorial", "Complete comparison contains only eligible editorial paths")
        if selected := component(changes):
            return Plan(selected, f"Complete comparison is contained in the explicit {selected} boundary")
        return Plan("full", "Cross-cutting, validation or unknown PR changes")
    except (EvidenceUnavailable, subprocess.SubprocessError, OSError, UnicodeError,
            json.JSONDecodeError, KeyError, TypeError) as error:
        # Expected missing/invalid read evidence never grants a reduced lane.
        # Execution failures remain outside this selector and fail the job.
        detail = str(error) if isinstance(error, EvidenceUnavailable) else type(error).__name__
        return Plan("full", f"{detail}; full validation required")


def main() -> None:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    repository = Repository(ROOT)
    plan = choose(repository, os.environ["GITHUB_EVENT_NAME"], event, os.environ["GITHUB_SHA"])
    print(json.dumps(asdict(plan), indent=2))
    if destination := os.environ.get("GITHUB_OUTPUT"):
        with Path(destination).open("a") as stream:
            stream.write(f"profile={plan.profile}\n")
    if destination := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(destination).open("a") as stream:
            stream.write(f"### Portable validation: {plan.profile}\n\n{plan.reason}.\n\n")
            if plan.profile == "main":
                stream.write("Tests ran on the pull request; this push runs the structural checks only.\n")
            stream.write("Selected checks must pass; native/gameplay qualification is separate.\n")


if __name__ == "__main__":
    main()
