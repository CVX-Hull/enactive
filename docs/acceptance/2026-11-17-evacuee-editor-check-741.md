---
owner: lead
status: historical
kind: run
date: '2026-11-17'
scope: 'One approved Evacuee menu-only check with corrected capture headroom'
---

# Evacuee editor check (#741)

## At a glance

The actor created the fresh world Regent with default options, entered Custom
Character and reached the Description tab showing **Scenario: Evacuee**. The
actor finished in the editor before starting gameplay. This completes the
[approved setup check](https://github.com/CVX-Hull/enactive/issues/741). Fresh
gameplay, save and reload, and seven-day acceptance remain open in
[#145](https://github.com/CVX-Hull/enactive/issues/145).

## Frozen scope

The owner approved one windowed admission up to $1.25, with a $0.75
provider-reported threshold, 24 combined attempts and 12 minutes of custody.
It used one Terra actor with v18 knowledge. Source was
`569a1c5a2bb2c4ce0168ef2227571613b011614b`, session
`f69d4efd27e2429aab1e2b0abb4c85fc` and manifest SHA-256
`35cded730ff66ac57ea62471d3d0370dfa44abaf82caaf90ff5928f6ca3c1740`.
The exact package passed the offline preflight with 256 MiB of capture space
and a 128 MiB ending threshold. It reused the setup path from
[#734](https://github.com/CVX-Hull/enactive/issues/734) and the
[#738](https://github.com/CVX-Hull/enactive/issues/738) capture-budget correction.

## Visible result

In the private package's `sources` directory, frame 5 shows Regent in the
world-creation dialog and frame 62 shows Regent in the World menu. Frame 65
shows Custom Character highlighted as the actor sends Enter with operation
`00ae36fd939e4b5f895de45af18c3be9`. Frame 197 shows Evacuee highlighted
in the Scenario tab. The actor sends Enter in operation
`3ef7d8c7d31e4bcf99e16132b68c1c84` and returns frame 198. It then navigates
to the Description tab. Operation `4491166755424810ab891b7347b8fa53`
returns frame 204, which shows **Scenario: Evacuee** and the prompt to finish
character creation. This is the final native operation in the store. The
actor follows it with a `task_complete` report.

## Accounting and cleanup

The [run ledger](../../data/evaluation/runs.jsonl) records the exact
OpenRouter-returned subtotal and attempts for study 741. One recall was
aborted when the actor ended. OpenRouter returned no usable charge for that
attempt, which remains unknown.

The watcher verified terminal supervision coverage without a Pause.
The custodian recorded `player_task_complete_unassessed` and revoked input
authority. The deciding host quiesced and native cleanup sent SIGTERM.
The lead verified the owned process groups and listeners were absent and
acquired the shared game lock. The archived userdir contained the Regent
world setup files and no survivor save.

The [private evidence seal](../../data/evidence/index.json) preserves the
original package and frames, operations, host trace, terminal receipts,
evaluation store, owned userdir and launch log. The log came from
`/tmp/enactive-741.UIv29o/supervisor.log`. The lead verified every seal hash
and checked these duplicate paths against the seal before removing them.

- `.runtime/computer-sessions/evacuee-setup-check-f69d4efd27e2429aab1e2b0abb4c85fc`
- `.runtime/evaluations/f69d4efd27e2429aab1e2b0abb4c85fc`
- `.runtime/archive/userdir-20261118T034025128887Z`
- `.runtime/user`, which matched the archive's `user` directory
