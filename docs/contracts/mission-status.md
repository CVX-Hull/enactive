---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Passive mission and deciding-host status

`/api/status.mission` is null or a copied bounded mission snapshot: objective, actor,
epoch, phase/cause, active operation/skill/progress, exact source/receipt identifiers,
remaining limits/reserve, unresolved effects, memory version and diagnostic.
Sibling `/api/status.deciding_host` is a passive, non-authorizing projection of
the exact mission's canonical driver preparation outputs, not mission state.
`current` binds host evidence to the mission snapshot's actor; `original` retains
predecessor evidence. `successor` is null or separately assignment-bound evidence,
including before Claim, with `mission_adoption_observed` describing actor equality
in that snapshot. Each reported host is unreported, launch_reported, exited,
timed_out, interrupted or exit_unresolved, with observed timestamps/returncode
where available. No launch receipt establishes current liveness, and a predecessor
exit does not rule out future succession. Missing, partial, malformed or mismatched
outputs remain unreported/unknown. A final matching driver report may say
`no_continuing_host_reported` only when every reported launch has a matching resolved
exit; unresolved or uncovered successor launches cannot establish that conclusion.
Driver outcome is unreported, incomplete or terminal, never gameplay acceptance.
The spectator displays assigned successor/adoption separately and marks disconnected
evidence last reported. No PIDs, command arguments, local paths or secrets are
forwarded by this projection; rendering grants no Claim, readmission or Resume.
`coordinate_scope` is nullable passive metadata derived from the current retained
normal-play source's adopted timeline: mission ID, session and coordinate epoch.
Normal source publication verifies adoption and creates the current session map;
status reuses that scope after the existing retained-source integrity check,
without repeating lifecycle verification or observing native state. It is null
before adoption, without that map or retained source, and at menus without a
current normal-play source. The coordinate epoch
is the adopted session's timeline index, **not** the mission/actor `epoch`, Pause
generation or native revision. A successor copies this returned scope for bound
context retrieval instead of guessing an index. It grants no freshness, lease,
claim or Resume, and the live handoff guard still validates the request against
its own checkpoint-derived scope. Current persisted formats and tool argument shapes are
unchanged. The diagnostic string retains earlier refused-operation errors after
later successes; inspect current operation results and phase/ownership/provenance
before concluding that a historical string is a current fatal fault. The
spectator uses mission Observe and disables ordinary input/Resume/recovery while
nonterminal; malformed mission state stays locked and Pause remains available.
At a terminal mission, recorded last-command errors are labeled historical;
controller/native snapshot diagnostics are explicitly not gameplay instructions.
Their complete text remains visible, including genuine faults. Current local
transport/manual errors remain separate. These labels neither establish that a
fault is stale nor reconcile unknown effects or authorize Resume.
Rendering sends no gameplay or memory request. Normal native input can still take
over; it is not an automatic mission continuation.

`memory_context` is the nullable last durably journaled bounded context packet, copied
for historical inspection. It is query-specific and includes as-of/version/source
IDs, tagged claims/work, omissions and dispositions; status never recomputes it or
claims that its old `current` labels are current now. `spent_inputs` is primitive
cost, not model decisions. A known `not_dispatched` or rejected primitive cannot
change a Claim/Work premise; excluding it from potential effects does not refresh
an old source, align another session or refund its charged admission. Prepared,
published, returned and unknown primitives still require outcome assessment.

`metrics.operations` groups all retained ledger requests by kind, skill and current
state; it excludes read-only calls and pre-admission rejections. `metrics.primitives`
counts every charged admission by current disposition, including rejection,
nondelivery and unknowns. SQLite supplies these cumulative projections at mission
publication; status reads the copied cache, never recent events or journal scans.
Neither metric counts delivered keys, model requests or independent tasks.
`model_requests`, `tool_calls` and `interventions` are null until measured. External
tokens, model time, quota and spending also remain unknown where unavailable.

`activity_phase` is a nullable summary of the current private paused activity:
origin request, checkpoint, stage, interrupt owner and whether it was answered.
It grants no authority, clears on Pause/revocation, and cannot be reconstructed
from `progress.phase`, which is the last reported historical result. The viewer
separates these records and shows bounded readable memory plus raw context;
truncated previews direct the reader to that raw packet. Repeated identical
packets keep their DOM so polling does not reset reading/selection. The source
cache is not a new memory history store. Native/independent-player acceptance
stays separate from the [synthetic viewer inspection](../acceptance/2026-10-20-mission-observer.md).

## Mission CLI, observation deadline and admission gate

Trusted Python `observe_mission(deadline_monotonic, timeout)` uses the original
absolute deadline through command-lock admission and native publication. It grants
no input capability and is absent from public command JSON. A timed queue refusal
is explicit; it never starts another relative timeout after the root expires.
It returns the exact response and its original exchange receipt time as a pair.
Later status captures cannot replace the retained response or renew that receipt.

The CLI exposes `mission-request --request PATH` for a current typed record directly
in project `.runtime/mission-requests/`, regular JSON only, no symlink/script or
arbitrary file path. It checks the same bounded schema before authenticated HTTP,
with no evaluation or implicit retry. Accepted is an admission acknowledgment;
request the immutable operation result by ID and inspect actual sources/effects.
Reusing an ID requires exactly the same payload. Missing network response does not
prove nondelivery. A retained delivery receipt cannot prove semantic success.

The admission gate excludes new mission Start while any raw HTTP command/recovery
is unsettled; raw admission cannot slip past a pending Start. It registers counts
under a short standard lock and rejects busy admission instead of queueing. Native
ordinary/recovery exchanges remain independent under controller channel locks.
While a nonterminal mission exists, raw Observe/input/recovery reject; use the
current typed mission path. Pause and cached status bypass this gate. Raw commands
also bind their original host generation before reading the body, so a delayed
Resume cannot adopt a later Pause. The generation is a trusted Python argument,
not a public JSON field. Terminal history remains visible and owns no execution.

[Contract index](../protocol.md).
