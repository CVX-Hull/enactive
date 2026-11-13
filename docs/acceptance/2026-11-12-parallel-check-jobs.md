---
owner: lead
status: historical
date: '2026-11-12'
scope: 'Hosted measurements of 12 November 2026 for splitting the pull-request check into parallel jobs (#557), the bar they were held to, the five-job shape that was built, the local checks run on it and the GitHub probes still pending; no game was launched and no paid call was made'
---

# Parallel jobs behind the required check, 12 November 2026

The [proposal](../design/parallel-check-jobs.md) for
[#557](https://github.com/CVX-Hull/enactive/issues/557), the cost of the pull-request
check, asked for a hosted measurement before anything was built. The owner approved
measuring the split and building it if it cleared the bar. This record holds the
measurements, what was built and what is still to be shown on GitHub. The
[CI profiles page](../workflows/ci-profiles.md#jobs-of-the-check) carries the current
rules.

## The bar

From the proposal: build only if the median of five hosted runs is at or under
2 minutes 45 seconds (165 seconds), and a documents-only check takes no longer than
it did with one job (about one minute).

## Measurements

All runs are full-profile runs on GitHub's hosted `ubuntu-24.04` runner, on a
throwaway workflow on the branch `ci-lane-measurement`, which is never merged. Times
are wall seconds for the whole run.

| Shape | Jobs | Runs (s) | Median (s) | Against the 165 s bar |
| --- | --- | --- | --- | --- |
| One job, as on main | `controller` runs everything | about 240; six earlier runs took 203, 220, 238, 243, 298 and 301 | about 240 | Starting point |
| Three lane jobs | `structure-and-python`, `adapter`, one `browser` job running its three suites in turn, then `controller` | 168, 168, 169, 170, 161 | 168 | Missed by 3 s |
| Five lane jobs | The same, with `browser` as one job for each of its three suites | 132, 126, 113, 117, 108 | 117 | Cleared by 48 s |

In the three-job shape the `browser` job bounded the run at about 160 seconds. In
the five-job shape, across its five runs:

| Job | Wall time (s) |
| --- | --- |
| `structure-and-python` | 97 to 113 |
| `adapter` | 90 to 127 |
| Each `browser` suite | 39 to 80 |
| `controller` | 2 to 3 |

The documents-only half of the bar was not measured on the throwaway workflow, which
ran the full profile only. It is the documents-only probe below.

The measurement workflow differs from the built one in two ways that add time to
every lane job: its adapter and browser jobs made a shallow checkout, and no job
selected a profile. The built lane jobs each fetch the complete history and run
`tools/ci.py` first. The first hosted runs of the built workflow show what that costs.

## What was built

The five-job shape, in one change:

- `.github/workflows/check.yml`: the lane jobs `structure-and-python`, `adapter` and
  `browser` (a matrix over `test_viewer`, `test_investigation` and
  `test_investigation_session`), and `controller`. Every lane job always runs,
  selects the profile itself and installs by step conditions on that profile.
  `controller` needs every lane job, runs under `always()` and passes only if every
  recorded result is `success`. Triggers, concurrency, permissions, pinned actions,
  hash-checked installs without install scripts and the Chrome AppArmor step are as
  they were.
- `tools/ci.py`: the table of lanes for each profile, the adapter lane's test file
  and the browser suites, shared by the checker and the tests.
- `tools/check.py`: `--lane` runs one lane's part of a profile and `--suite` one
  browser suite. A lane the profile does not use prints that it has nothing to do
  and exits 0; a profile with no row in the lane table is refused. Without `--lane`
  the command runs the whole profile as before. The Markdown parsers are imported
  on first use, so the file loads on the standard library alone: the browser lane
  runs it on the runner's Python with no lockfile, and the adapter lane does the
  same when it has nothing to do.
- Tests: the workflow policy tests in `tests/test_ci.py`, and in
  `tests/test_devtools.py` the lane tests of the checker and a test that the Python
  and adapter lanes together collect exactly the tests of the full profile.

What each lane job installs, by profile ("none" means the job goes straight from
selecting the profile to reporting that it has nothing to do):

| Lane job | Full | Viewer | Editorial | Main |
| --- | --- | --- | --- | --- |
| `structure-and-python` | Python lockfile, root Node packages, player-host and curator-host Node packages | The same | Python lockfile, root Node packages | Python lockfile, root Node packages |
| `adapter` | Python lockfile, player-host Node packages | None | None | None |
| Each `browser` job | Root Node packages, Chrome and its AppArmor profile | The same | None | None |

Every lane job also sets up Python 3.14 and Node 22 from the runner's tool cache,
and the first two create an empty project environment. The structural checks need
the lockfile and the root Node packages (the document anchor slugger). The Python
tests need both hosts' Node packages, because `tests/test_player_host_contract.py`
and `tests/test_curator_host.py` skip their cases without them. The browser suites
need Node, the root packages, Chrome and a system `python3`: their fixture server
uses the standard library only.

## Local checks

On the change, in a worktree of main at `c40184d`, on macOS, with the project
environment and all three Node installs present:

| Command | Result |
| --- | --- |
| `tools/check.py` (whole full profile) | Passed: 1010 passed and 8 skipped in pytest; browser suites 6, 14 and 20 tests passed |
| `tools/check.py --profile full --lane structure-and-python` | Passed: structural checks, then 1009 passed and 8 skipped |
| `tools/check.py --profile full --lane adapter` | Passed: 1 passed |
| `tools/check.py --profile full --lane browser --suite S`, for each suite | Passed: 6, 14 and 20 tests |
| `tools/check.py --profile viewer --lane structure-and-python` | Passed: structural checks, then 49 passed |
| `tools/check.py --profile editorial --lane adapter`, and `--lane browser --suite test_viewer` | Each printed that the lane has nothing to do in the editorial profile, ran nothing and exited 0 |
| `tools/check.py --profile main --lane structure-and-python` | Passed: structural checks only, no test command |
| `python3 -I -S tools/check.py --profile viewer --lane browser --suite test_viewer` | Passed on a Python with no installed packages: 6 tests |

The Python lane's 1009 passed and 8 skipped plus the adapter lane's 1 passed equal the
whole profile's 1010 passed and 8 skipped. The partition test compares the collected
test IDs rather than these totals. Each workflow policy test and the partition test
failed when the workflow or the lane commands were altered against it: a weaker or
missing `controller` condition, a dropped needed job, a job-level condition on a lane,
a dropped host install, a missing timeout, an ignored failure, a conditional checker
step, a shallow checkout, and a Python lane that kept or dropped a test file.

The `controller` step's shell lines were run locally under `bash -e`: they exit 0 for
three `success` results and non-zero for a `failure`, `cancelled` or `skipped` result
and for an empty list. How GitHub fills that list is for the probes.

## Probes on GitHub

The lead runs these on throwaway pull requests, closed without merging, and fills
the table. Until then the rows are pending and the built workflow has not been shown
to behave as intended on GitHub.

| Probe | Expected | Run | Result |
| --- | --- | --- | --- |
| Failing Python test | `structure-and-python` fails and `controller` is red | pending | pending |
| Failing adapter test | `adapter` fails and `controller` is red | pending | pending |
| Failing browser test | That suite's `browser` job fails, the other two finish, and `controller` is red | pending | pending |
| Run cancelled by hand | `controller` is red on the current head, not skipped | pending | pending |
| Second push | The first run is cancelled and no green `controller` from it stands on the new head | pending | pending |
| Documents-only change | Editorial profile; `adapter` and every `browser` job report that they have nothing to do; `controller` is green in about one minute or less | pending | pending |
| Viewer-only change | Viewer profile; `adapter` reports that it has nothing to do; `controller` is green | pending | pending |
| Push to main | Main profile; only `structure-and-python` does work; `controller` is green | pending | pending |

The same runs settle what could not be checked locally about waiting for the check:

- whether `gh pr checks <PR> --watch` can end after the lane jobs and before
  `controller` is listed;
- that `gh run list --workflow check.yml --commit <HEAD-SHA>` finds a pull request's
  run by its head commit, and `gh run watch <RUN> --exit-status` ends non-zero for a
  failed and for a cancelled run;
- that auto-merge queued while the lane jobs run merges only after `controller`
  passes;
- that the runner image provides `python` and Python 3.14 as today, so the browser
  jobs can run the checker without a project environment.

## Limits

- `controller` trusts the recorded result of each job. It does not inspect what a
  job ran; the workflow policy tests and the partition test are what tie a green job
  to the work it should have done.
- The hosted timings are from the measurement workflow, not from the built one, and
  run times on the hosted runner vary by tens of seconds.
- The workflow file was parsed as YAML and checked by the policy tests. No
  Actions-specific linter is installed in the project, and none was added.
