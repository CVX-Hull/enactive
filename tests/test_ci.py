"""Profile selection over real temporary Git history."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from tools import ci


class ProfileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "-q", "-b", "main")
        self.write("README.md", "Base\n")
        self.write("harness/example.py", "value=1\n")
        self.parent = self.commit("base")
        self.write("harness/example.py", "value=2\n")
        self.candidate = self.commit("feature")
        self.main = self.squash()
        self.repository = ci.Repository(self.root)
        self.event = dict(ref="refs/heads/main", before=self.parent, after=self.main)

    def git(self, *arguments, input=None):
        return subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *arguments], cwd=self.root,
            input=input, capture_output=True, check=True, text=True).stdout.strip()

    def write(self, name, value):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)

    def commit(self, message):
        self.git("add", "--all")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def squash(self):
        tree = self.git("rev-parse", "HEAD^{tree}")
        merged = self.git("commit-tree", tree, "-p", self.parent, "-m", "ordinary squash")
        self.git("update-ref", "HEAD", merged)
        return merged

    def pr(self, base=None, head=None, target="main"):
        return dict(pull_request=dict(base=dict(ref=target, sha=base or self.parent),
                                      head=dict(sha=head or self.candidate)))

    def test_every_main_push_runs_the_structural_main_profile(self):
        for path in ("harness/other.py", "tools/check.py", ".github/workflows/check.yml", "docs/overview.md",
                     "unexpected.bin"):
            with self.subTest(path=path):
                self.git("reset", "--hard", self.main)
                self.write(path, "Changed\n")
                after = self.commit("any change")
                plan = ci.choose(self.repository, "push", dict(ref="refs/heads/main", before=self.main, after=after),
                                 after)
                self.assertEqual(plan.profile, "main")

    def test_editorial_complete_pr_comparison(self):
        before = self.main
        self.write("docs/research-ci.md", "Evidence\n")
        after = self.commit("editorial")
        self.assertEqual(ci.choose(self.repository, "pull_request", self.pr(base=before, head=after), after).profile,
                         "editorial")

    def test_earlier_source_commit_cannot_hide_behind_last_editorial_commit(self):
        self.write("docs/research-ci.md", "Later editorial\n")
        after = self.commit("last editorial")
        plan = ci.choose(self.repository, "pull_request", self.pr(head=after), after)
        self.assertEqual(plan.profile, "full")

    def test_rename_delete_and_file_modes_preserve_both_sides(self):
        before = self.main
        (self.root / "docs").mkdir()
        self.git("mv", "harness/example.py", "docs/research-hidden.md")
        after = self.commit("rename source")
        changed = self.repository.changes(before, after)
        self.assertEqual({value.path for value in changed}, {"harness/example.py", "docs/research-hidden.md"})
        self.assertEqual(ci.choose(self.repository, "pull_request", self.pr(base=before, head=after), after).profile, "full")
        self.git("reset", "--hard", before)
        (self.root / "README.md").unlink()
        (self.root / "README.md").symlink_to("harness/example.py")
        linked = self.commit("symlink")
        self.assertFalse(self.repository.changes(before, linked)[0].regular)
        self.assertEqual(ci.choose(self.repository, "pull_request", self.pr(base=before, head=linked), linked).profile, "full")

    def test_unsupported_events_and_checkout_mismatch(self):
        for name, event in (("workflow_dispatch", {}), ("pull_request", self.pr(target="other")),
                            ("pull_request", {}), ("push", {**self.event, "ref": "refs/heads/other"}),
                            ("push", {**self.event, "after": self.parent})):
            with self.subTest(name=name, event=event):
                self.assertEqual(ci.choose(self.repository, name, event, self.main).profile, "full")
        with self.assertRaisesRegex(RuntimeError, "another candidate"):
            ci.choose(self.repository, "push", self.event, self.parent)

    def test_document_scope_matches_checked_markdown_and_regular_assets(self):
        for name in ("README.md", "AGENTS.md", "docs/player-guide.md", "docs/protocol.md",
                     "docs/setup.md", "docs/runbook.md", "docs/engineering.md", "docs/project-management.md",
                     "docs/research-ci.md", "docs/acceptance/report.json", "docs/assets/example.png"):
            with self.subTest(name=name): self.assertTrue(ci.editorial(name))
        for name in (".github/pull_request_template.md", "elsewhere.md", "docs/diagrams/player.svg",
                     "docs/acceptance/run.py", "docs/assets/script.js",
                     ".github/workflows/check.yml"):
            with self.subTest(name=name): self.assertFalse(ci.editorial(name))

    def test_component_complete_comparisons_run_selected_scope_on_a_pr(self):
        for path in ("web/app/app.css", "web/app/main.js"):
            self.git("reset", "--hard", self.main)
            self.write(path, "Changed")
            self.write("docs/architecture.md", "Current explanation")
            after = self.commit("contained")
            with self.subTest(path=path):
                self.assertEqual(ci.choose(self.repository, "pull_request", self.pr(base=self.main, head=after),
                                           after).profile, "viewer")

    def test_component_cannot_hide_crosscutting_files_renames_or_nonregular_objects(self):
        def change(path, after="100644"):
            return ci.Change(path, "100644", after)
        for paths in (("harness/movement.py", "web/app/main.js"),
                      ("web/app/main.js", "harness/server.py"),
                      ("harness/movement.py", "tests/test_controller.py"),
                      ("harness/movement.py", "schemas/gameplay.schema.json"),
                      ("web/app/app.css", "tools/check.py"), ("web/app/app.css", "unknown")):
            with self.subTest(paths=paths): self.assertIsNone(ci.component([change(p) for p in paths]))
        self.assertIsNone(ci.component([change("web/app/main.js", "120000")]))
        self.assertIsNone(ci.component([]))
        before = self.main
        self.write("web/app/main.js", "Source")
        base = self.commit("viewer source")
        (self.root / "docs").mkdir(exist_ok=True)
        self.git("mv", "web/app/main.js", "docs/renamed.md")
        head = self.commit("rename")
        # Both sides participate: deleting the viewer source is still viewer scope.
        self.assertEqual(ci.choose(self.repository, "pull_request", self.pr(base=base, head=head), head).profile, "viewer")
        self.git("reset", "--hard", before)
        self.git("mv", "harness/example.py", "web/app/main.js")
        head = self.commit("cross boundary rename")
        self.assertEqual(ci.choose(self.repository, "pull_request", self.pr(base=before, head=head), head).profile, "full")

    def test_main_reports_the_closed_profile_without_running_tests(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "event").write_text(json.dumps(self.event))
            environment = dict(GITHUB_EVENT_PATH=str(directory / "event"), GITHUB_EVENT_NAME="push",
                GITHUB_SHA=self.main, GITHUB_OUTPUT=str(directory / "output"),
                GITHUB_STEP_SUMMARY=str(directory / "summary"))
            with patch.dict(os.environ, environment), patch.object(ci, "Repository", return_value=self.repository):
                ci.main()
            self.assertEqual((directory / "output").read_text(), "profile=main\n")
            self.assertIn("Tests ran on the pull request", (directory / "summary").read_text())

    def test_deleted_editorial_file_and_odd_filename_use_native_complete_diff(self):
        before = self.main
        (self.root / "README.md").unlink()
        self.write("docs/research-line\nbreak.md", "Research\n")
        after = self.commit("editorial deletion and newline")
        event = self.pr(base=before, head=after)
        self.assertEqual(ci.choose(self.repository, "pull_request", event, after).profile, "editorial")
        self.assertEqual({change.path for change in self.repository.changes(before, after)},
                         {"README.md", "docs/research-line\nbreak.md"})


_PROFILE = "steps.validation.outputs.profile"
_IS = re.compile(rf"{re.escape(_PROFILE)} == '([a-z]+)'(?: \|\| {re.escape(_PROFILE)} == '([a-z]+)')*")
_IS_NOT = re.compile(rf"{re.escape(_PROFILE)} != '([a-z]+)'(?: && {re.escape(_PROFILE)} != '([a-z]+)')*")


def runs_in(step: dict, profile: str) -> bool:
    """Whether a workflow step runs for a profile. A step condition may only list profiles it runs in
    (`== 'a' || == 'b'`) or profiles it does not run in (`!= 'a' && != 'b'`)."""
    condition = step.get("if")
    if condition is None:
        return True
    named = set(re.findall(r"'([a-z]+)'", condition))
    if _IS.fullmatch(condition):
        return profile in named
    if _IS_NOT.fullmatch(condition):
        return profile not in named
    raise AssertionError(f"Unsupported step condition: {condition}")


class WorkflowPolicyTests(unittest.TestCase):
    """The required check stays truthful when its work is spread over several jobs (R-WRONG-MERGE)."""

    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        # BaseLoader retains Actions' `on` key without YAML1.1 boolean coercion;
        # actionlint validates Actions syntax. These are our policy invariants.
        self.workflow = yaml.load((root / ci.WORKFLOW).read_text(), Loader=yaml.BaseLoader)
        self.jobs = self.workflow["jobs"]
        self.profiles = ("full", "editorial", "main", *ci.COMPONENT_TESTS)

    def installs(self, lane, text):
        steps = [step for step in self.jobs[lane]["steps"] if text in step.get("run", "") + step.get("name", "")]
        self.assertEqual(len(steps), 1, (lane, text))
        return steps[0]

    def test_triggers_permissions_and_the_job_set(self):
        self.assertEqual(self.workflow["on"]["pull_request"], dict(branches=["main"]))
        self.assertEqual(self.workflow["on"]["push"], dict(branches=["main"]))
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(self.jobs), {*ci.LANES, "controller"})
        self.assertEqual(set(ci.PROFILE_LANES), set(self.profiles))  # a profile without a row is refused
        for name, job in self.jobs.items():
            with self.subTest(job=name):
                self.assertIn("timeout-minutes", job)
                self.assertNotIn("continue-on-error", job)
                self.assertTrue(all("continue-on-error" not in step for step in job["steps"]))

    def test_controller_always_runs_and_passes_only_if_every_other_job_succeeded(self):
        controller = self.jobs["controller"]
        self.assertEqual(set(controller["needs"]), set(self.jobs) - {"controller"})
        # A skipped job satisfies a required check, and anything weaker than always() skips this one
        # when a lane fails or the run is cancelled.
        self.assertEqual(controller["if"], "always()")
        self.assertEqual(len(controller["steps"]), 1)  # no checkout or setup that could fail first
        step = controller["steps"][0]
        self.assertNotIn("if", step)
        self.assertNotIn("uses", step)
        self.assertEqual(step["env"], {"RESULTS": "${{ join(needs.*.result, ' ') }}"})
        # Run the step itself: it passes only for one success per needed job, and for nothing else.
        lanes = len(controller["needs"])
        cases = {" ".join(["success"] * lanes): 0, " ".join(["success"] * (lanes - 1) + ["failure"]): 1,
                 " ".join(["success"] * (lanes - 1) + ["cancelled"]): 1, " ".join(["success"] * (lanes - 1) + ["skipped"]): 1,
                 " ".join(["success"] * (lanes - 1)): 1, " ".join(["success"] * (lanes + 1)): 1, "": 1, "   ": 1}
        for results, expected in cases.items():
            with self.subTest(results=results):
                done = subprocess.run(["bash", "-eo", "pipefail", "-c", step["run"]], env={"RESULTS": results, "PATH": os.environ["PATH"]},
                                      capture_output=True, timeout=30)
                self.assertEqual(min(done.returncode, 1), expected)

    def test_every_lane_job_always_runs_selects_the_profile_and_runs_its_lane(self):
        for lane in ci.LANES:
            with self.subTest(lane=lane):
                job = self.jobs[lane]
                self.assertNotIn("if", job)  # a lane with nothing to do says so; it is never skipped
                self.assertNotIn("needs", job)
                steps = job["steps"]
                checkout = steps[0]
                self.assertTrue(checkout["uses"].startswith("actions/checkout@"))
                self.assertEqual(checkout["with"], {"fetch-depth": "0"})  # the selector compares complete history
                selector = next(step for step in steps if step.get("id") == "validation")
                self.assertEqual(selector["run"], "python tools/ci.py")
                self.assertNotIn("if", selector)
                checks = steps[-1]
                self.assertEqual(checks["env"]["VALIDATION_PROFILE"], "${{ steps.validation.outputs.profile }}")
                self.assertIn(f'tools/check.py --profile "$VALIDATION_PROFILE" --lane {lane}', checks["run"])
                self.assertNotIn("if", checks)
                self.assertEqual([step for step in steps if "check.py" in step.get("run", "")], [checks])
                for step in steps:  # only the selected profile decides what a lane installs
                    for profile in self.profiles:
                        runs_in(step, profile)
        browser = self.jobs["browser"]
        self.assertEqual(browser["strategy"], {"fail-fast": "false", "matrix": {"suite": list(ci.BROWSER_SUITES)}})
        self.assertEqual(browser["steps"][-1]["env"]["BROWSER_SUITE"], "${{ matrix.suite }}")
        self.assertIn('--suite "$BROWSER_SUITE"', browser["steps"][-1]["run"])

    def test_a_lane_installs_what_its_work_needs_in_every_profile_that_gives_it_work(self):
        lockfile, root_packages = "--require-hashes -r requirements-dev.lock", '.cache/npm" ci --ignore-scripts'
        needs = {
            "structure-and-python": (lockfile, root_packages),
            "adapter": (lockfile, "--prefix tools/player_host ci --ignore-scripts"),
            "browser": (root_packages, "puppeteer browsers install chrome", "Allow the project Chrome sandbox"),
        }
        for lane, texts in needs.items():
            for profile in self.profiles:
                if lane in ci.PROFILE_LANES[profile]:
                    for text in texts:
                        with self.subTest(lane=lane, profile=profile, install=text):
                            self.assertTrue(runs_in(self.installs(lane, text), profile))
        # Two Python test files skip their cases without a host's packages; a lane that left an install
        # out would pass while running fewer tests.
        for profile in ("full", *ci.COMPONENT_TESTS):
            for host in ("player_host", "curator_host"):
                with self.subTest(profile=profile, host=host):
                    install = self.installs("structure-and-python", f"--prefix tools/{host} ci --ignore-scripts")
                    self.assertTrue(runs_in(install, profile))


if __name__ == "__main__":
    unittest.main()
