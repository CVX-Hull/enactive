---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Ordinary delivery receipts and observation continuation

A correlated ready ACK is returned delivery even for unfamiliar or superseded
evidence. Authenticate it before fallible acceptance, journaling or retention,
then settle once with its actual `source_after` or explicit `evidence_loss` before
Pause/current publication. The ledger's bounded `native_ack` contains protocol,
id, session, revision, status, native error, paused/pause origin, takeover,
timestamp, frame validity/identity and boundary. Scene/UI/geometry remain in the
original archive/controller journal. Separate `processing_error` and `evidence_loss`
never rewrite known delivery as unknown. Publication bookkeeping failure can bind
the native UUID atomically while settling the prepared intent. When that mandatory
settlement commits and custody/evidence remain healthy, the publication diagnostic
does not itself force Pause. Raw controller processing faults, lost archive/current
evidence and lifecycle proof failures still stop. SQLite owns the row transaction; no redundant post-ACK preflight-file sweep or second journal is
required. Failed storage remains failed storage: reopening without durably saved
ACK evidence is conservative. A returned receipt without after evidence stops
with explicit loss and cannot construct a gameplay/2 PrimitiveResult requiring it.

ACK retention is historical and non-promoting: it preserves bytes, identity,
original receipt clocks and recorded lag without changing current source/session/
generation. `source_after` always names that ACK capture. A separately validated
actual current snapshot preserves its first receipt and pays its own frame/byte
cost when distinct. It never replaces after. A different current source ends the
operation partial and stops a text batch even when pixels match. Healthy native
advancement beyond the retained ACK also ends the batch and requires Observe;
the actual ACK and its receipt remain unchanged. An owned prompt
advances only from eligible actual current evidence, retaining root, Work, consent,
deadlines and costs while clearing incompatible focus/quantity assertions.
After known returned direct input, an absent or aged independent snapshot can
retain a read-only ordinary scope. Its checkpoint remains the entry source; the
ACK remains historical. The private scope records the exact authenticated operation
generation, preserving root, Work, actor/epoch, game anchor, deadlines, consent and
cumulative costs. Its PhaseReceipt stage is `awaiting_observation`, status marks
`observation_needed` and exposes no current source. At writer consumption, skills
and lifecycle requests refuse without input, charges or a new Pause. Explicit
Observe verifies that generation, unchanged store lineage, retained integrity and
all existing custody/global limits before capturing and publishing a fresh binding.
It clears the read-only marker, advances an actual menu or closes on actual normal
return; a locally exhausted root instead gets the immutable [`macro_closure` receipt](operation-observation.md).
It never renews old-source authority or resumes a failed lease. Healthy local
game-time overshoot returns partial work (`macro_exhausted`), retaining mission
ownership; normal return ends that root and an owned menu awaits Observe closure.
An exhausted ordinary prompt child is refused before operation rotation or
controller input preflight, with `macro_exhausted` and no primitive charge.
This applies to ordinary and semantic roots, without recognizing a menu type.
The original root and prompt remain unchanged until explicit Observe commits
their closure. Custody, retained-source integrity and global limits must still
pass; local exhaustion cannot hide their failure. Refusal does not choose a new
root, close a menu or establish task success.
Request/root allowance exceptions are typed separately from mission, clock,
storage and authority failures. A trusted read-only classifier can translate only
eligible, healthy ordinary-scope expiry into the controller's existing known
unpublished refusal. The controller checks fatal ownership/Pause/competing-work/
boundary/capture fences before preserving custody, including at final atomic
publication. It never classifies a published request this way. Any allocated but
unpublished admission must be removed successfully; a prepared primitive keeps
its original charge and settles not-dispatched. The existing authenticated
rotation records a read-only `awaiting_observation` scope; explicit Observe still
owns fresh evidence and any macro closure. Lifecycle, registered activity/recovery
and actual global exhaustion are excluded. Passive terminal verification may
establish a skill's result before declining an additional input proposal.
The same known-unpublished path covers final-preflight filename churn for
ordinary leased semantic key/action proposals, including an activity's START at
normal play. It does not cover paused activity/recovery or lifecycle input.
The controller preserves its actual preflight capture and checks all fatal
guards before rejecting; it neither retargets the native frame nor retries.
Before retaining read-only lineage, the writer independently verifies current
custody, original source/storage health, mission limits and the receipt's actual
preflight state and clocks. A rejected status alone is insufficient: early
image/geometry refusals can precede controller preparation. Navigation reports
`awaiting_observation` both before movement and after a verified prefix; that
prefix and every prepared charge remain recorded. Only explicit Observe and a
new player choice can continue; no old suffix resumes. Source regressions cover
these cases; an actual native occurrence and complete campaign remain separate.

An authenticated published native rejection also retains this read-only scope
for ordinary leased semantic actions, navigation and menu choices. The primitive keeps its
original charge and rejected ACK, with no after-frame or inferred effect. The
writer checks the same custody, source/storage, clock and global-limit guards;
the error text does not classify the continuation. Explicit Observe is required
before a fresh decision, even when the rejection leaves the visible state unchanged.
Aged semantic evidence cannot turn that known nondelivery into unknown. This
excludes lifecycle, registered activity/recovery and any processing/evidence fault.

Unknown delivery, actual clock/session regression, controller processing,
integrity/storage, lifecycle/activity/recovery and global exhaustion keep their
stopping paths. A missing current frame alone neither undelivers an ACK nor
permits another scalar. These are source-tested paths; new native/graphical
qualification remains pending.


The native's exact cached rejected response may remain visible until explicit
Observe. A private pending-observation pointer selects its already settled logical
primitive; the writer verifies the owning root/child, source and original native
mapping. Only read-only checks may match that exact projected ACK instead of a
ready response. They still require a valid frame/receiver and unchanged native,
controller, Pause, takeover, store and mission custody. No response is rewritten
as ready. Actual Observe must return ready evidence before publishing any new
binding and clears the private pointer. Reopen does not restore this allowance;
ordinary input admission remains ready-only.

[Contract index](../protocol.md).
