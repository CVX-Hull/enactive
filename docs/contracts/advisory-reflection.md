---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Asynchronous reflection and advice

This protocol owns the current asynchronous integration boundary; the
[procedure/exchange design](../design/procedure-learning.md) retains rationale and
remaining proposals. Current records use reflection/3. One private
RegisteredReflection composes a per-admission
passive mailbox/cache with the existing writer and SQLite ledger. Four routine
root skills or original-request age coalesce a job. Capacity is the smaller of
job count and whole charged windows; routine credits accrue over the greater of
original wall/input progress, with one future slot available to urgent failures,
recovery and handoff. The exact deterministic policy is:

- `capacity=min(jobs,floor(total_seconds/job_seconds))`.
- `progress=max(clamp((now-started_at)/(deadline-started_at)),clamp(spent_inputs/admitted_inputs))`,
  with each fraction clamped to0..1 and all allowances from original admission.
- `earned=min(capacity,1+floor(progress*capacity))`; routine total jobs cannot
  exceed earned, urgent total jobs cannot exceed `min(capacity,earned+1)`.
- Routine eligibility needs four root skills or oldest new request age at least
  `min(job_seconds,(deadline-started_at)/(capacity+1))`, measured from original
  `admitted_at`. Urgency bypasses this threshold, never finite capacity/credits.

Capacity conservatively reserves whole claim windows. Original pending, ledger
job/time limits and claim costs remain independently enforced. Reopen/handoff
does not reset progress, jobs or costs. Rationale and rejected formulas are in
[brief064](../changes/064-execution-first-learning.md#horizon-allocation-and-software-waiting).
This bounds early consumption; it does not guarantee useful reflection or use
extra game inputs to earn work. Oldest/latest rows and then older exceptions
receive priority before normal rows, including during byte fitting. Each job retains original request/result order and
cutoff, memory version, bounded sources/procedures and explicit omissions.
`requests_per_job` bounds selected trajectory records, not tool RPCs; job count
and each claimed job's original wall window are separate finite limits.
Interrupted missing results and individually oversized rows remain omitted
original evidence rather than preventing subsequent review. Pending overload
coalesces future work; exhausting finite reflection limits leaves it unreviewed.
Summary `unreviewed_requests` counts new uncovered rows and `omitted_requests`
counts historical bounded-context omissions; neither claims model attention.

The existing loopback server exposes authenticated `/api/reflection/command`,
`result`, `next`, `source`, `frame` and `proposal` routes. Passive reads/waits use
cached data and retained source images without the input queue/lock or Observe.
Only the passive `next` read permits up to40 seconds, using the existing condition
notification to return promptly on work or closure. Other transport/tool waits
remain at most15 seconds. The adapter caps claim/collection at15 seconds and the
remaining original call allowance; no job window or resource limit is renewed.
The default player's60-second MCP timeout is unchanged. The optional frozen
[adviser profile](../operations/player-host.md) can hold idle waiting in software across these polls; it
does not extend execution or claim deadlines or promise a hard wall deadline.
Only the existing writer applies claims/submissions. Claims charge their original
finite wall window without refund; software receipt time judges submission
lateness separately from writer queue delay. Rejected advisory commands retain
zero-input outcomes; storage faults remain faults. Original command receipts
restore into a passive cache without requeueing. No model computation runs there.

Structured tools expose `enactive_reflect_next`, `enactive_reflect_source`,
`enactive_reflect_submit`, `enactive_reflect_result` and `enactive_advice`.
The result tool collects an original command ID even after an adapter loses its
volatile claimed-job cache. Advisory source reads do not populate the player's
source-read cache. Candidate proposals never auto-adopt, Resume or confer input
authority; the player owns adoption, applicability and later choices.

The sole model-facing submission authors semantic Procedure fields, code and
support; software supplies canonical IDs, family/revision and original admission
environment through the shared authoring helper. Qualified parent selection is
limited to procedures in that original claimed job. Original job/cutoff/support
closure and durable writer checks still apply. Notes require no candidate or
status read. Candidate authoring reads the original mission's admission environment
off the deciding path; it never infers it from a donor or another mission.

`enactive_advice(snapshot_id,proposal_index=null)` exposes at most the latest four
proposal summaries with original indexes; an exact index reveals full detail.
The bound is to the selected snapshot, not a live latest lookup. Explicit
`enactive_remember` with `entry_type=procedure_candidate`, `proposal_index` and
`candidate_index` selects an original candidate read for that exact snapshot in
this SDK. Software submits its existing canonical body through ordinary Procedure
memory admission, preserving automatic identity joins. Unread/evicted/mismatched
selection refuses; stale lineage/environment/source checks remain with the writer.
No auto-adoption, success claim or per-procedure lead approval is introduced.
Old model advice/authoring shapes reject; canonical records and machine APIs retain
their current contracts.

The optional exported adviser profile waits through idle responses in software,
within both its frozen wait window and original mission deadline. It changes no
claim window or budget, repeats only idle, propagates cancellation after the
existing finite in-flight call and preserves temporary sealing/handoff semantics.
Default player waiting remains unchanged. Profile export does not install or
launch a host; actual qualification remains a separate lane.

Normal finalization temporarily seals advisory ingress before draining received
commands and settling offered/claimed bookkeeping as unreviewed/unknown. It
preserves costs and original outcomes, and does not claim the host actor stopped.
While finishing or temporarily sealed, next-job reads offer no work and retain
their original bounded wait before returning `idle`. Only a terminal mission phase
or permanent writer shutdown returns `closed`; temporary sealing never tells an
advisory actor to terminate. A canceled preterminal finish, including refusal at
the authoritative terminal ledger write, reopens healthy nonterminal ingress
without renewing old jobs. The settled advisory phase is published before the
Finish result becomes collectable. Storage faults and already committed terminal
history never reopen. Ordinary Save/Exit/Load does not seal advisory ingress.
Permanent shutdown wakes waiting readers; terminal history accepts no late writes.
Actual host concurrency, actor quiescence and real discovery/reuse/counterexample/
fresh-context/overlapping-play qualifications remain separate delivery057 work.

[Contract index](../protocol.md).
