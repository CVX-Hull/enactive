"""Profile selection over real temporary Git history and bounded API fixtures."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from tools import ci


class FixtureRepository(ci.Repository):
    def __init__(self, root, responses):
        super().__init__(root, "owner/project")
        self.responses, self.reads = responses, []

    def api(self, path, **query):
        self.reads.append((path, query))
        value = self.responses[path]
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)

    def git(self, *arguments):
        if arguments[:2] == ("fetch", "--no-tags"):
            # The fixture already retains this exact PR-head Git object; no
            # network or original branch-name lookup supplies another source.
            if arguments != ("fetch", "--no-tags", "origin", "refs/pull/1/head"):
                raise AssertionError(arguments)
            return ""
        return super().git(*arguments)


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
        self.responses = {
            f"commits/{self.main}/pulls": [dict(number=1, merge_commit_sha=self.main, merged_at="2026-10-24T20:00:00Z")],
            "pulls/1": dict(merged=True, merge_commit_sha=self.main, merged_at="2026-10-24T20:00:00Z",
                base=dict(ref="main", sha=self.parent), head=dict(sha=self.candidate)),
            "actions/workflows/check.yml": dict(id=7, path=ci.WORKFLOW, state="active"),
            "actions/workflows/7/runs": dict(workflow_runs=[dict(id=8, workflow_id=7, path=ci.WORKFLOW,
                event="pull_request", head_sha=self.candidate, status="completed", conclusion="success",
                created_at="2026-10-24T19:00:00Z", pull_requests=[])]),
            "actions/runs/8/jobs": dict(total_count=1, jobs=[dict(name="controller", status="completed",
                conclusion="success", head_sha=self.candidate, steps=[dict(name="Run strict full validation",
                    status="completed", conclusion="success")])]),
        }
        self.repository = FixtureRepository(self.root, self.responses)
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

    def choose(self):
        return ci.choose(self.repository, "push", self.event, self.main)

    def pr(self, base=None, head=None, target="main"):
        return dict(pull_request=dict(base=dict(ref=target, sha=base or self.parent),
                                      head=dict(sha=head or self.candidate)))

    def test_same_tree_ordinary_merge_uses_latest_full_pr_coverage_without_pr_array(self):
        plan = self.choose()
        self.assertEqual(plan.profile, "main-smoke")
        self.assertEqual(plan.qualifying_run, "https://github.com/owner/project/actions/runs/8")
        self.assertEqual(self.repository.reads[-2][1], dict(event="pull_request", head_sha=self.candidate, per_page=1))
        self.assertEqual(self.repository.reads[-1][1], dict(filter="latest", per_page=100))
        self.assertNotEqual(self.main, self.candidate)

    def test_editorial_complete_pr_and_main_comparisons_need_no_api(self):
        before = self.main
        self.write("docs/research-ci.md", "Evidence\n")
        after = self.commit("editorial")
        for name, event in (("push", dict(ref="refs/heads/main", before=before, after=after)),
                            ("pull_request", self.pr(base=before, head=after))):
            with self.subTest(event=name):
                self.assertEqual(ci.choose(self.repository, name, event, after).profile, "editorial")
        self.assertEqual(self.repository.reads, [])

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

    def test_known_context_and_unknown_paths_never_get_main_reuse(self):
        for path in ("tools/ci.py", "tools/new_shared_helper.py", "tools/__init__.py", "tests/__init__.py",
                     ".github/workflows/check.yml", "requirements-dev.lock", "docs/control-registry.json",
                     "unexpected.bin"):
            with self.subTest(path=path):
                self.git("reset", "--hard", self.parent)
                self.write(path, "Changed\n")
                candidate = self.commit("context")
                plan = ci.choose(self.repository, "push", dict(ref="refs/heads/main", before=self.parent, after=candidate), candidate)
                self.assertEqual(plan.profile, "full")
        self.assertEqual(self.repository.reads, [])

    def test_latest_failed_cancelled_skipped_or_incomplete_run_cannot_borrow_old_green(self):
        original = deepcopy(self.responses["actions/workflows/7/runs"])
        for changes in (dict(conclusion="failure"), dict(conclusion="cancelled"), dict(conclusion="skipped"),
                        dict(status="in_progress"), dict(head_sha="a"*40), dict(event="push"),
                        dict(workflow_id=99), dict(path="other.yml")):
            self.responses["actions/workflows/7/runs"] = deepcopy(original)
            self.responses["actions/workflows/7/runs"]["workflow_runs"][0].update(changes)
            with self.subTest(changes=changes): self.assertEqual(self.choose().profile, "full")

    def test_original_run_must_precede_merge_and_rerun_keeps_its_original_event(self):
        run = self.responses["actions/workflows/7/runs"]["workflow_runs"][0]
        for value in (None, "invalid", "2026-10-24T20:00:00", "2026-10-24T20:00:00Z", "2026-10-24T20:00:01Z"):
            run["created_at"] = value
            with self.subTest(value=value): self.assertEqual(self.choose().profile, "full")
        run.update(created_at="2026-10-24T19:00:00Z", run_attempt=2, run_started_at="2026-10-24T21:00:00Z")
        self.assertEqual(self.choose().profile, "main-smoke")

    def test_expected_current_attempt_controller_and_complete_job_page_are_required(self):
        page = self.responses["actions/runs/8/jobs"]
        original = deepcopy(page)
        for changes in (dict(conclusion="skipped"), dict(conclusion="failure"), dict(conclusion="cancelled"),
                        dict(status="queued"), dict(name="unrelated"), dict(head_sha="a"*40)):
            page.clear(); page.update(deepcopy(original)); page["jobs"][0].update(changes)
            with self.subTest(changes=changes): self.assertEqual(self.choose().profile, "full")
        page.clear(); page.update(deepcopy(original)); page["total_count"] = 2
        self.assertEqual(self.choose().profile, "full")
        page["total_count"] = 2; page["jobs"] *= 2
        self.assertEqual(self.choose().profile, "full")

    def test_source_tree_base_association_and_checkout_mismatch_refuse_reuse(self):
        pr = self.responses["pulls/1"]
        pr["head"]["sha"] = self.parent
        self.assertEqual(self.choose().profile, "full")
        pr["head"]["sha"] = self.candidate
        pr["base"]["sha"] = "a"*40
        self.assertEqual(self.choose().profile, "full")
        pr["base"]["sha"] = self.parent
        associations = self.responses[f"commits/{self.main}/pulls"]
        associations *= 2
        self.assertEqual(self.choose().profile, "full")
        associations.clear()
        self.assertEqual(self.choose().profile, "full")
        with self.assertRaisesRegex(RuntimeError, "another candidate"):
            ci.choose(self.repository, "push", self.event, self.parent)

    def test_a_successful_editorial_run_is_not_full_coverage_even_at_the_same_head(self):
        controller = self.responses["actions/runs/8/jobs"]["jobs"][0]
        original = deepcopy(controller["steps"])
        for steps in ([], [dict(name="Run strict editorial validation", status="completed", conclusion="success")],
                      [{**original[0], "conclusion": "skipped"}], [{**original[0], "conclusion": "failure"}],
                      [{**original[0], "conclusion": "cancelled"}], [{**original[0], "status": "in_progress"}],
                      original * 2):
            controller["steps"] = steps
            with self.subTest(steps=steps): self.assertEqual(self.choose().profile, "full")

    def test_empty_missing_bad_events_and_api_errors_fall_back_without_execution(self):
        for name, event in (("workflow_dispatch", {}), ("pull_request", self.pr(target="other")),
                            ("pull_request", {}), ("push", {**self.event, "before": "0"*40}),
                            ("push", {**self.event, "ref": "refs/heads/other"}),
                            ("push", {**self.event, "before": self.main})):
            with self.subTest(name=name, event=event):
                self.assertEqual(ci.choose(self.repository, name, event, self.main).profile, "full")
        self.responses[f"commits/{self.main}/pulls"] = subprocess.CalledProcessError(1, ["gh"])
        self.assertEqual(self.choose().profile, "full")

    def test_document_scope_matches_checked_markdown_and_regular_assets(self):
        for name in ("README.md", "AGENTS.md", "docs/player-guide.md", "docs/protocol.md",
                     "docs/setup.md", "docs/runbook.md", "docs/engineering.md", "docs/project-management.md",
                     "docs/research-ci.md", "docs/acceptance/report.json", "docs/assets/example.png",
                     "docs/diagrams/current.mmd", "docs/diagrams/rendered.json"):
            with self.subTest(name=name): self.assertTrue(ci.editorial(name))
        for name in (".github/pull_request_template.md", "elsewhere.md", "docs/diagrams/config.json",
                     "docs/control-registry.json", "docs/acceptance/run.py", "docs/assets/script.js",
                     ".github/workflows/check.yml"):
            with self.subTest(name=name): self.assertFalse(ci.editorial(name))

    def test_component_complete_comparisons_run_selected_scope_on_pr_and_main(self):
        for path, profile in (("harness/movement.py", "movement"), ("web/style.css", "viewer"),
                              ("web/app.js", "viewer"), ("tests/test_movement.py", "movement")):
            self.git("reset", "--hard", self.main)
            self.write(path, "Changed")
            self.write("docs/architecture.md", "Current explanation")
            after = self.commit("contained")
            for name, event in (("push", dict(ref="refs/heads/main", before=self.main, after=after)),
                                ("pull_request", self.pr(base=self.main, head=after))):
                with self.subTest(path=path, event=name):
                    self.assertEqual(ci.choose(self.repository, name, event, after).profile, profile)
        self.assertEqual(self.repository.reads, [])

    def test_component_cannot_hide_crosscutting_files_renames_or_nonregular_objects(self):
        def change(path, after="100644"):
            return ci.Change(path, "100644", after)
        for paths in (("harness/movement.py", "web/app.js"),
                      ("web/app.js", "harness/server.py"),
                      ("harness/movement.py", "tests/test_controller.py"),
                      ("harness/movement.py", "schemas/gameplay.schema.json"),
                      ("web/style.css", "tools/check.py"), ("web/style.css", "unknown")):
            with self.subTest(paths=paths): self.assertIsNone(ci.component([change(p) for p in paths]))
        self.assertIsNone(ci.component([change("web/app.js", "120000")]))
        self.assertIsNone(ci.component([]))
        before = self.main
        self.write("web/app.js", "Source")
        base = self.commit("viewer source")
        (self.root / "docs").mkdir(exist_ok=True)
        self.git("mv", "web/app.js", "docs/renamed.md")
        head = self.commit("rename")
        # Both sides participate: deleting the viewer source is still viewer scope.
        self.assertEqual(ci.choose(self.repository, "pull_request", self.pr(base=base, head=head), head).profile, "viewer")
        self.git("reset", "--hard", before)
        self.git("mv", "harness/example.py", "web/app.js")
        head = self.commit("cross boundary rename")
        self.assertEqual(ci.choose(self.repository, "pull_request", self.pr(base=before, head=head), head).profile, "full")

    def test_main_reports_closed_profile_and_existing_evidence_without_running_tests(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "event").write_text(json.dumps(self.event))
            environment = dict(GITHUB_EVENT_PATH=str(directory / "event"), GITHUB_REPOSITORY="owner/project",
                GITHUB_EVENT_NAME="push", GITHUB_SHA=self.main, GITHUB_OUTPUT=str(directory / "output"),
                GITHUB_STEP_SUMMARY=str(directory / "summary"))
            with patch.dict(os.environ, environment), patch.object(ci, "Repository", return_value=self.repository):
                ci.main()
            self.assertEqual((directory / "output").read_text(), "profile=main-smoke\n")
            self.assertIn("not rerun in main-smoke", (directory / "summary").read_text())

    def test_deleted_editorial_file_and_odd_filename_use_native_complete_diff(self):
        before = self.main
        (self.root / "README.md").unlink()
        self.write("docs/research-line\nbreak.md", "Research\n")
        after = self.commit("editorial deletion and newline")
        event = self.pr(base=before, head=after)
        self.assertEqual(ci.choose(self.repository, "pull_request", event, after).profile, "editorial")
        self.assertEqual({change.path for change in self.repository.changes(before, after)},
                         {"README.md", "docs/research-line\nbreak.md"})

    def test_checkout_merge_base_and_api_page_incompleteness_cannot_grant_reuse(self):
        self.event["before"] = self.candidate
        self.assertEqual(self.choose().profile, "full")
        self.event["before"] = self.parent
        associated = self.responses[f"commits/{self.main}/pulls"]
        associated *= 100
        self.assertEqual(self.choose().profile, "full")

    def test_unrelated_head_ancestry_cannot_replace_the_original_candidate(self):
        unrelated = self.git("commit-tree", self.git("rev-parse", "HEAD^{tree}"), "-m", "unrelated root")
        self.responses["pulls/1"]["head"]["sha"] = unrelated
        self.assertEqual(self.choose().profile, "full")


class WorkflowPolicyTests(unittest.TestCase):
    def test_required_workflow_establishes_the_selector_platform_assumptions(self):
        root = Path(__file__).resolve().parents[1]
        # BaseLoader retains Actions' `on` key without YAML1.1 boolean coercion;
        # actionlint validates Actions syntax. These are our policy invariants.
        value = yaml.load((root / ci.WORKFLOW).read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(value["on"]["pull_request"], dict(branches=["main"]))
        self.assertEqual(value["on"]["push"], dict(branches=["main"]))
        self.assertEqual(set(value["jobs"]), {"controller"})
        job = value["jobs"]["controller"]
        self.assertNotIn("if", job)
        self.assertNotIn("continue-on-error", job)
        steps = job["steps"]
        self.assertTrue(all("continue-on-error" not in step for step in steps))
        checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
        self.assertEqual(checkout["with"]["fetch-depth"], "0")
        self.assertNotIn("ref", checkout["with"])
        selector = next(step for step in steps if step.get("id") == "validation")
        self.assertEqual(selector["run"], "python tools/ci.py")
        checks = next(step for step in steps if "VALIDATION_PROFILE" in step.get("env", {}))
        self.assertEqual(checks["name"], "Run strict ${{ steps.validation.outputs.profile }} validation")
        self.assertEqual(checks["env"]["VALIDATION_PROFILE"], "${{ steps.validation.outputs.profile }}")
        self.assertIn('--profile "$VALIDATION_PROFILE"', checks["run"])
        self.assertNotIn("if", checks)
        self.assertEqual(value["permissions"], {"contents": "read", "actions": "read", "pull-requests": "read"})


if __name__ == "__main__":
    unittest.main()
