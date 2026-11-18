---
owner: lead
status: historical
kind: run
date: '2026-11-17'
scope: 'One approved Evacuee menu-only check interrupted before its first input by the frozen capture-byte allowance'
---

# Evacuee setup check (#737)

## At a glance

The [approved admission](https://github.com/CVX-Hull/enactive/issues/737) stopped at
the title menu before world creation or scenario selection. The lead set the total
capture allowance too low for the planned observe-then-input sequence. The
approval has been used. The Evacuee verification and seven-day outcome in
[#145](https://github.com/CVX-Hull/enactive/issues/145) remain open.

## Frozen scope

The owner approved one windowed admission under a $1.25 envelope, ending in
the editor before play. The frozen package allowed one Terra actor with v18
knowledge, 24 aggregate attempts, a $0.75 provider-reported threshold and 12
minutes of custody. The [#734 reconstruction](https://github.com/CVX-Hull/enactive/issues/734)
supplied the setup brief. Source was
`5dfdd5c25c4bdf46b64464685af6f39fac184eca`, session
`993dfda863db4282ad5981fd623467cf` and manifest SHA-256
`c45aa5ec5c3ff6302d30282e31d9c111b47562e718344aaeb997d06ef3a8016d`.
The package passed offline validation before launch on the prepared native
target and a fresh options-only userdir.

## Observed stop

The actor's observation `f6b91b50c6cf44529252592600b44361` returned frame 2,
which showed the New Game menu with Preset Character highlighted. The
actor then requested two Right keys to open the World menu.
Its public result reported a service error with `submission: "none"` and
operation ID `3e4258e454fb4d0f96318fdd7e45f920`. Exact-ID collection returned
“Unknown original operation for this actor.” The actor sent no further input
and issued a direct `cannot_continue` report.

The driver retained the stop origin `Original capture reservation exhausted`.
Frame 2 used 12,802 bytes of the fixed 67,108,864-byte budget. The [runtime
reservation](../../harness/computer/runtime.py) requires room for a full
64 MiB capture before it records or dispatches another operation.
Only the initial observation appears in the operation store. The store has zero
input charges, one retained frame and no navigation operation. The fence was
therefore a predictable consequence of the selected allowance. Offline package
validation accepted the field values without detecting that sequence conflict.
This admission supplied no new evidence for character setup or an adapter
input defect.

## Accounting and cleanup

The [run ledger](../../data/evaluation/runs.jsonl) records the exact
OpenRouter subtotal and attempt counts for study 737. The watcher recorded a
terminal custodian receipt and verified supervision coverage. The receipt's
disposition is `interrupted`, with revoked input authority, quiescent deciding
host and absent native process. Native cleanup sent SIGTERM.
The lead independently checked the exact owned groups and three listeners
and verified the shared game lock was available. The archived userdir contained
no created world or survivor save.

The [private evidence seal](../../data/evidence/index.json) preserves the
package, frame and operation stores, player and terminal receipts, launch log,
evaluation store and owned userdir. The lead verified every hash before retiring
the four duplicate working paths.

- `.runtime/computer-sessions/evacuee-setup-check-993dfda863db4282ad5981fd623467cf`
- `.runtime/evaluations/993dfda863db4282ad5981fd623467cf`
- `.runtime/archive/userdir-20261118T025940936812Z`
- `.runtime/user`, which matched the archive's `user` directory

The launch log came from `/tmp/enactive-evacuee-live.sD2t4j/supervisor.log`.
The evidence index gives the supervisor's source checkpoint for that log.
The next setup check needs enough byte
headroom for already retained PNGs and the runtime's original pending-capture
reservation, and separate approval for a fresh package.
[#738](https://github.com/CVX-Hull/enactive/issues/738) owns the offline follow-up.
