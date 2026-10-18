---
owner: lead
status: historical
date: 2026-10-17
scope: Round 011 controller ownership, portable races and manual real-game acceptance; no autonomous player or live-model evaluation
---

# Controller run ownership — round 011

Round 011 delivers [#50](https://github.com/CVX-Hull/cdda-player/issues/50), the
controller lease portion of #36. One explicit in-process owner can send observed
semantic actions. Competing remote inputs reject, and Pause revokes ownership.
The existing spectator shows the owner and preserves operator takeover. The
service still does not instantiate the passive supervisor or connect a provider.
[Brief](../changes/011-controller-run-lease.md),
[current contract](../protocol.md#controller-run-ownership),
[manifest](2026-10-17-controller-run-lease-manifest.json).

## Source and review

Base main `c1ba24480a73bdcf9dd8b48a54a2701c6038d1c2`; reviewed brief checkpoint
`128478bcbb96ab594406c56a117733e7cea5972e`. One isolated worker owned only
controller.py and its tests, returning `044d5ab1a10463dc8893f7f4fe1aa96f1a488262`,
integrated as `0a5b0ad`. Lead owned HTTP regressions, viewer disclosure, docs,
diagrams, integration and all shared native runtime. Native acceptance identifies
runtime file hashes separately from the commit because documentation and viewer
integration were still in the working tree. The final candidate must retain those
runtime hashes; GitHub records exact protected-head and merged-main CI publication.

Two source sweeps supported splitting controller ownership from receipt/service
integration. Independent brief review approved. Independent integrated code review
found no P1/P2 defects and independently passed 82 controller/HTTP tests and viewer
regressions using isolated bridges. Visual review found two wording defects:
Resume after transport failure needed reconciliation, and generic “errors” wrongly
suggested a rejected competing command revokes its owner. Both were corrected and
the diagram regenerated and inspected. These reviews do not replace native proof.

Portable evidence: 64 controller tests including 18 new ownership tests; 82 combined
controller/HTTP tests; 332 Python tests in the common command, plus viewer, import,
document, diagram, governance and whitespace checks. Cases include simultaneous
acquisition, active/queued writers, stale/reconstructed capabilities, old queued
walk generations, Pause around publication/claim, recovery, timeout/malformed
results, explicit reconciliation retaining unknowns, and shutdown without restore.
Public JSON cannot supply a lease. Viewer tests cover owner disclosure, blocked
ordinary input, available Observe/Pause and revoked-but-paused state.

## Real graphical acceptance

The existing installed native binary SHA-256 is
`e3c022b5da440d2e4a31fc537ea07c988c2a767bf96197b83de4c7224d47bf87`.
Native bridge, header, source pin and patcher hashes match round009, and owned build
extraction matches current native source. No rebuild was needed. The prepared
wrapper used the explicit project userdir and FULLSCREEN=no. The browser spectator
showed actual native frames; no mock image, hidden state, save editing or engine
validation bypass supplied an outcome.

A local manual acceptance driver owns the real Controller and existing Server.
It is an evidence tool, not a production supervisor or supported lifecycle API.
Receipts and original frames are under `.runtime/evidence/round011/native/`.

| Probe | Recorded result |
| --- | --- |
| Normal task context | Recovery Eight / Morgan Vale loaded normally. `009` reconciled the new world at relative origin `(0,0,0)`; adjacent visible floor and no visible creatures supported the explicitly chosen two-step probe. |
| Acquisition and competing input | `012`–`016`: fresh observation, exact lease acquisition; external action and walk rejected without moving or removing the owner. |
| Leased movement | `017` RIGHT moved `(0,0,0)`→`(1,0,0)`, revision 13→15; `018` LEFT returned to `(0,0,0)`, revision 15→17. Exact native action UUIDs and original PNGs are retained. No general task-completion claim follows. |
| Browser takeover | The actual spectator showed RUN OWNED and disabled Resume. Its Pause button revoked ownership; `019` showed null lease and `020` rejected the old capability without movement. Leased and paused screenshots were inspected and retained. |
| Explicit manual recovery | `021`–`024`: Observe then Resume restored ordinary input with null lease; inventory opened through the ordinary action path. |
| Menu exclusion | `025`: acquisition at the inventory menu rejected with a normal-play-frame requirement. |
| Release | `027`–`032`: fresh acquisition then explicit release paused and removed ownership; the released capability rejected without movement. |

The initial load command `008` timed out at a world transition. The following
Observe established current state, preserved the uncertain old admission and did
not replay loading. This was not counted as a successful transport result. Known
historical gameplay/control unknowns remained visible in the spectator throughout.
Normal save-and-quit required explicit user confirmation after automatic approval
review rejected an initial save command; the rejected command was not delivered.
The user authorized normal saving. The save confirmation `040` also timed out
across the world transition; `041` showed the normal main menu in a new session.
The uncertainty was retained rather than relabeled as a successful receipt. Normal
quit was then requested. Cleanup results are retained in the manifest.

Native final-commit timing races were not newly instrumented. New queue/lease races
are portable tests; prior native final-gate evidence remains scoped to
[round008](2026-10-17-native-recovery-planner.md). No live provider, API spending,
autonomous task execution, new skill, semantic monitor or survival claim is included.

## Maintenance and failures

The worker's initial implementation had two portable failures from overly strict
payload validation: changed missing-expectation diagnostics and an existing Resume
caller with known observation fields. One repair preserved the current command
field contract while rejecting unknown fields and capability injection; subsequent
64-test runs passed. The first local diagram render failed because the sandbox
could not launch the browser; the authorized project-local rerun passed. These
failures were retained, not reported as native evidence. The first acceptance
manifest used an incorrect shape and was rejected by the existing schema; the
generator was corrected to the current manifest v1 without changing the schema.

The 1050-pixel ownership diagram was inspected for labels and authority paths.
Existing tools and locks were sufficient; no global packages, profiles or application
settings changed. Evidence remains local and ignored, with hashes in the manifest;
a fresh checkout lacks the original media. Retain originals for review, never
silently delete them or user saves. Final publication/closure is recorded in GitHub.

#36 retains exact passive-intent/native-receipt assembly, explicit service task
lifecycle, provider/configuration/spend and #23 task-status integration. #10 now
explicitly tracks the higher-level player that turns broad objectives into bounded
tasks, within aggregate limits and evidence-based completion. Controller ownership
is a prerequisite, not completion of either outcome. Revisit these controls on new
ingress, lease/lifecycle changes or relevant failures; broader maintenance remains #13.
