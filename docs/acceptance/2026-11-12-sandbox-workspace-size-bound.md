---
owner: lead
status: historical
date: '2026-11-12'
scope: 'Removal of the curator sandbox''s volume-wide free-space guard on the owner''s decision of 12 November 2026 (#556), leaving the bound on the session''s own files as the only disk control; source tests only, no curator session with a model'
---

# Curator sandbox bounds its own files, not the volume, 12 November 2026

## What was removed and why

The curator sandbox's supervisor read the free space of the whole volume before launch
and on every poll. It refused to launch a session when the reading left too little
headroom, and it stopped a running session when free space fell below a floor: the
first reading minus the session's 1 GiB disk allowance and a 1 GiB margin.

On 11 November 2026 that guard ended a paid curator session after 67 seconds. The
session's own writable directories had measured zero bytes, and about 150 GB was free
when the disk was checked afterwards. The
[record of that stop](2026-11-11-p1-storage-stop-178.md) says the observations
"establish neither a full disk nor attribution of the decline". Any other program that
wrote 2 GiB during a session could trip the guard, and nothing the session did could
prevent it. A guard that blocks work without preventing a defect is a trigger for
review under the [control rule](../standards/authority.md#control-review).

Removed from `harness/curator/sandbox.py`, with every reading of volume free space:

- the launch refusal `insufficient volume free space` and the stop `volume free-space floor`;
- `disk unmeasurable` as the result of a failed volume read (it remains the stop for a
  writable tree that cannot be measured);
- the `free_space_margin_bytes` limit and the `volume_space` readings in the sandbox result.

## What bounds disk use

One control, which existed before this change and is unchanged: the supervisor totals
the allocated size of every file under the directories the profile lets the session
write (the workspace's `submissions/`, `drafts/` and `scratch/`, and its fresh home),
without following links, ten times a second. Above the limit (1 GiB by default) it stops
the session's process tree with `disk limit`. The kernel limits each file to 64 MiB.
The [operator page](../operations/curator-hosts.md#what-the-sandbox-bounds) states the
bounds.

What the sandbox does not bound:

- **The rest of the disk.** Other programs' disk use neither stops a session nor is
  limited by it.
- **Deleted files held open.** Their space is not under any directory, so the total does
  not see it. The removed guard was the only thing that could catch it. What remains is
  the kernel's per-file and open-file limits: 64 MiB times 256 files, about 16 GiB for
  each of at most 64 processes. No session is recorded doing this.

## Owner's decision

The 12 November control review listed the guard as a candidate on
[issue #556](https://github.com/CVX-Hull/enactive/issues/556) with the proposal to bound
the workspace's own size only. The owner decided the same day to remove it
([decision comment](https://github.com/CVX-Hull/enactive/issues/556#issuecomment-6841405914)).

## Records and names

Session records stop carrying `provenance.volume_space`, and shadow summaries stop
carrying `sandbox.volume_space`. No tracked code read either value; the shadow runner
only copied the first into the second. `container-manifest/1` and `curator-shadow/1`
keep their versions: the key was a diagnostic of the removed guard, listed in no schema
and required by no reader. No reader enumerates stop reasons, so the two retired reasons
needed no migration. Session records already written, and the three public receipts
under `docs/acceptance/assets/` that hold the old readings, are unchanged.

## What was and was not verified

Verified on this Mac, on the change's branch:

- The six curator test files passed, 221 tests with none skipped. They include the
  macOS Seatbelt lane with real sandboxed children: a child writing past a 16 MiB bound
  is stopped with `disk limit`, an unmeasurable tree is stopped, and temporary-file
  churn below the bound is not a breach.
- New portable tests: the supervisor stops a session at the first reading above the
  bound and not at the bound itself; a volume reporting no free space neither refuses
  nor stops a session, and the supervisor does not read it; the measurement counts the
  writable directories and the home and follows no link out of them. The second of these
  fails against the earlier supervisor.
- The whole Python suite passed: 1,007 passed and 8 skipped, all eight for sealed
  evidence absent from the checkout. The fast structural check passed.

Not verified:

- No curator session ran with a real host or model, and no paid or network model call
  was made.
- The hosted Linux check does not run the Seatbelt lane.
- The size of the deleted-but-open gap was reasoned from the limits, not measured.
