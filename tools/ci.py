"""Choose strict validation using existing Git/GitHub evidence; never cache green."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
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
_CONTEXT = {
    "AGENTS.md", "CONTRIBUTING.md", "pyproject.toml", "package.json", "package-lock.json",
    ".puppeteerrc.cjs", "tests/__init__.py", "docs/control-registry.json", "docs/controls.md",
    "docs/engineering.md", "docs/project-management.md", "docs/documentation.md", "docs/charter.md",
    "docs/diagrams/config.json", "docs/diagrams/browser.json",
}


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
    qualifying_run: str | None = None


def editorial(path: str) -> bool:
    value = PurePosixPath(path)
    if path == "README.md":
        return True
    if value.parent == PurePosixPath("docs") and value.name.startswith("research") and value.suffix == ".md":
        return True
    if path.startswith("docs/changes/") and value.suffix == ".md":
        return True
    if path.startswith("docs/acceptance/") and value.suffix in {".md", ".json", *_ASSETS}:
        return True
    if path.startswith("docs/assets/") and value.suffix in _ASSETS:
        return True
    return value.parent == PurePosixPath("docs/diagrams") and (
        value.suffix in {".mmd", ".svg"} or value.name == "rendered.json")


def validation_context(path: str) -> bool:
    # Engineering tools are deliberately coarse initially: no hand-maintained
    # dependency graph of future checker helpers or package bootstrap behavior.
    return (path in _CONTEXT or path.startswith((".github/", "tools/", "schemas/", "requirements")))


def known_main_source(path: str) -> bool:
    value = PurePosixPath(path)
    return (editorial(path) or validation_context(path)
        or path.startswith(("harness/", "tools/", "tests/", "web/"))
        or path.startswith("docs/") and value.suffix == ".md")


def _sha(value) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise EvidenceUnavailable("Missing or unsupported Git identity")
    return value


def _timestamp(value) -> datetime:
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.utcoffset() is None:
            raise ValueError("Missing timezone")
        return stamp
    except (TypeError, ValueError):
        raise EvidenceUnavailable("Missing original GitHub event time") from None


class Repository:
    def __init__(self, root: Path, name: str):
        self.root, self.name = root, name

    def command(self, arguments: list[str]) -> bytes:
        return subprocess.run(arguments, cwd=self.root, check=True, capture_output=True,
                              timeout=60).stdout

    def git(self, *arguments: str) -> str:
        return self.command(["git", *arguments]).decode().strip()

    def api(self, path: str, **query):
        arguments = ["gh", "api", "--method", "GET", f"repos/{self.name}/{path}"]
        for key, value in query.items():
            arguments.extend(("-f", f"{key}={value}"))
        return json.loads(self.command(arguments))

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

    def main_coverage(self, event: dict, changes: list[Change], head: str) -> Plan:
        if any(not change.regular or validation_context(change.path) or not known_main_source(change.path)
               for change in changes):
            raise EvidenceUnavailable("Changed validation context or unknown main paths")
        parents = self.git("rev-list", "--parents", "-n", "1", head).split()
        if len(parents) != 2 or parents[0] != head or parents[1] != event.get("before"):
            raise EvidenceUnavailable("Main push is not one ordinary single-parent merge")
        parent = parents[1]
        associated = self.api(f"commits/{head}/pulls", per_page=100)
        if len(associated) >= 100:
            raise EvidenceUnavailable("Incomplete pull request association page")
        matches = [pr for pr in associated
                   if pr.get("merge_commit_sha") == head and pr.get("merged_at")]
        if len(matches) != 1:
            raise EvidenceUnavailable("No unique merged pull request")
        number = matches[0].get("number")
        if type(number) is not int or number < 1:
            raise EvidenceUnavailable("Missing merged pull request identity")
        pr = self.api(f"pulls/{number}")
        if (pr.get("merged") is not True or pr.get("merge_commit_sha") != head
                or pr.get("base", {}).get("ref") != "main" or pr["base"].get("sha") != parent):
            raise EvidenceUnavailable("Merged pull request base differs from main parent")
        candidate = _sha(pr.get("head", {}).get("sha"))
        # Deleted source branches retain the PR head ref. Fetch the object, not
        # a user-supplied branch name, and let Git establish ancestry/tree facts.
        self.git("fetch", "--no-tags", "origin", f"refs/pull/{number}/head")
        if self.git("merge-base", parent, candidate) != parent:
            raise EvidenceUnavailable("PR head did not include the actual main base")
        if self.git("rev-parse", f"{candidate}^{{tree}}") != self.git("rev-parse", f"{head}^{{tree}}"):
            raise EvidenceUnavailable("Actual main tree differs from the tested candidate")
        workflow = self.api(f"actions/workflows/{PurePosixPath(WORKFLOW).name}")
        if workflow.get("path") != WORKFLOW or workflow.get("state") != "active":
            raise EvidenceUnavailable("Expected workflow is unavailable")
        runs = self.api(f"actions/workflows/{workflow['id']}/runs", event="pull_request",
                        head_sha=candidate, per_page=1).get("workflow_runs", [])
        if len(runs) != 1:
            raise EvidenceUnavailable("No latest candidate workflow run")
        run = runs[0]
        if (run.get("workflow_id") != workflow["id"] or run.get("path") != WORKFLOW
                or run.get("event") != "pull_request" or run.get("head_sha") != candidate
                or run.get("status") != "completed" or run.get("conclusion") != "success"
                or _timestamp(run.get("created_at")) >= _timestamp(pr.get("merged_at"))):
            raise EvidenceUnavailable("Latest pre-merge candidate run is not successful and applicable")
        if type(run.get("id")) is not int or run["id"] < 1:
            raise EvidenceUnavailable("Missing workflow run identity")
        job_page = self.api(f"actions/runs/{run['id']}/jobs", filter="latest", per_page=100)
        jobs = job_page.get("jobs", [])
        if job_page.get("total_count") != len(jobs):
            raise EvidenceUnavailable("Incomplete current-attempt job page")
        controllers = [job for job in jobs if job.get("name") == "controller"]
        if (len(controllers) != 1 or controllers[0].get("status") != "completed"
                or controllers[0].get("conclusion") != "success" or controllers[0].get("head_sha") != candidate):
            raise EvidenceUnavailable("Expected current-attempt controller did not succeed")
        full_steps = [step for step in controllers[0].get("steps", [])
                      if step.get("name") == "Run strict full validation"]
        if (len(full_steps) != 1 or full_steps[0].get("status") != "completed"
                or full_steps[0].get("conclusion") != "success"):
            raise EvidenceUnavailable("Successful full-profile execution is not recorded")
        url = f"https://github.com/{self.name}/actions/runs/{run['id']}"
        return Plan("main-smoke", "Same candidate tree received full validation before protected merge", url)


def choose(repository: Repository, event_name: str, event: dict, sha: str) -> Plan:
    head = _sha(sha)
    if repository.git("rev-parse", "HEAD") != head:
        # Full checks cannot repair validation of the wrong checkout.
        raise RuntimeError("Checkout differs from the event; refusing validation of another candidate")
    try:
        if event_name == "pull_request":
            pr = event.get("pull_request") or {}
            if pr.get("base", {}).get("ref") != "main":
                raise EvidenceUnavailable("Only main-targeting PRs have reduced validation")
            changes = repository.changes(pr["base"]["sha"], pr["head"]["sha"], merge_base=True)
        elif event_name == "push" and event.get("ref") == "refs/heads/main" and event.get("after") == head:
            changes = repository.changes(event.get("before"), head)
        else:
            raise EvidenceUnavailable("Unsupported event requires full validation")
        if changes and all(change.regular and editorial(change.path) for change in changes):
            return Plan("editorial", "Complete comparison contains only eligible editorial paths")
        if event_name == "push":
            return repository.main_coverage(event, changes, head)
        return Plan("full", "Source, mixed, control or unknown PR changes")
    except (EvidenceUnavailable, subprocess.SubprocessError, OSError, UnicodeError,
            json.JSONDecodeError, KeyError, TypeError) as error:
        # Expected missing/invalid read evidence never grants a reduced lane.
        # Execution failures remain outside this selector and fail the job.
        detail = str(error) if isinstance(error, EvidenceUnavailable) else type(error).__name__
        return Plan("full", f"{detail}; full validation required")


def main() -> None:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    repository = Repository(ROOT, os.environ["GITHUB_REPOSITORY"])
    plan = choose(repository, os.environ["GITHUB_EVENT_NAME"], event, os.environ["GITHUB_SHA"])
    print(json.dumps(asdict(plan), indent=2))
    if destination := os.environ.get("GITHUB_OUTPUT"):
        with Path(destination).open("a") as stream:
            stream.write(f"profile={plan.profile}\n")
    if destination := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(destination).open("a") as stream:
            stream.write(f"### Portable validation: {plan.profile}\n\n{plan.reason}.\n\n")
            if plan.qualifying_run:
                stream.write(f"Full regression coverage: {plan.qualifying_run}; not rerun in main-smoke.\n")
            stream.write("Selected checks must pass; native/gameplay qualification is separate.\n")


if __name__ == "__main__":
    main()
