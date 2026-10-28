---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Quiescent player replacement

The generic host settles when the actual MCP result contains a coherent current
completed handoff issuance, including explicit collection of a pending/uncertain
handoff originated by that host. A successor's read-only issuance retrieval does
not settle its host; ordinary collection errors retain their correction path.
It blocks later same-batch tool dispatch and ends the model turn without another
inference request or generated final report. This does not assign a successor:
the campaign driver independently validates the full issuance and fresh runtime
state before assignment. Incoherent claimed completion fails closed; fatal
cancellation, timeout and transport/cleanup errors override host success. See the
[host contract](../../tools/player_host/README.md) for the presentation binding.

`handoff` requires settled adopted normal play, the retained owned child, sole
runtime handle/empty queue and reconciled effects. It identifies up to32 retained
checkpoints and every unfinished Work item (up to16); completed/failed Work with
lost supporting bytes also needs attention. Classification uses the coherent Work
projection without truncation. Before stopping input, one shared checker bounds
classification, checkpoints and complete required support to127 distinct sources,
reserving the128th for the future post-Pause source. Required Work must fit a
complete96KiB packet;32KiB of the128KiB handoff envelope remains reserved for the
mission wrapper, maximum query and future source metadata. A narrowly typed
representation refusal sends no input and preserves the original lease, epoch and
bindings. Canonical `checkpoint_ids` identifies retained source observation IDs,
not memory Claim or Work IDs. MCP/PlayerTools authoring instead requires
`checkpoint_sources`: null binds the exact selected cached snapshot source; an
explicit ID requires a previously read source/image in this mission. Software
binds observation IDs without refresh, substitution or deduplication; missing,
foreign, duplicate resolved sources and the old authoring field refuse before
staging. Canonical receiver checks still apply. `unfinished_work_ids` identifies
the exact complete unfinished Work set. Unknown checkpoint references and omitted/extra Work IDs are correctable
draft errors before stopping input. The player selects actual retained sources or
retrieves complete current Work and submits a NEW explicit request while still
eligible. No handoff, source substitution, Resume or budget renewal is automatic.
A known checkpoint source with unavailable bytes remains an evidence failure. Actual
authority, storage and budget failures still stop. The runtime
internally stops input, clears the lease/bindings/map, captures the post-Pause normal
source and checks empty controller/native slots. Atomic issuance records that source,
controller boot, original operator Pause counter, host/native generations and a new
epoch. This is not a public user Pause or restored input authority.

Continue with [successor context, Claim and readmission](#successor-context-claim-and-readmission); [host activation](../operations/player-host.md) supplies the operating procedure.

## Successor context, Claim and readmission

Every `context` request has a required nullable `handoff` field. A successor sets
`{handoff_id, prospective_player_id, actor_role}` while the issuance is live and
unconsumed. Its exact wrapper is journaled and cached (last32), with the packet's
memory version. Ordinary predecessor retrieval uses null and keeps its32KiB,
16-source selective envelope. Bound successor retrieval instead returns every
required Work item, its complete source dispositions and all issuance checkpoints,
independently of query ranking or unrelated Claims, within128KiB/128sources/16Work.
Insufficient requested bytes fail explicitly; required Work is never omitted.
Raw Work assertions retain their eight-source bound. A distinct `WorkView` may
retain up to128 coherent premises, including incomparable or unavailable sources;
its historical/unknown state grants no current progress or input authority.
A claim references one
to four such packets at the current memory version, covering the issued and current
unfinished Work set. Work writes are frozen from issuance through claim until
readmission; permitted Claim corrections require fresh-version retrieval. Packets
retain explicit omissions/unknowns; unavailable old Work evidence is never upgraded
to current progress. A claim may declare up to128 retained sources from those
packets and issuance, including every checkpoint, the post-Pause source and retained support for required
Work. Source loss after retrieval requires a new packet with an explicit unknown
disposition; declaring a nonexistent source read cannot repair it. Classification,
Work support and read declarations share a per-operation128-distinct-source cache;
the exact live checkpoint guards still verify independently. Arbitrary evidence
loss can expand previously terminal Work and invalidate finite fit; preflight is
not a guarantee against later archive corruption. Oversized/lost support stays
explicitly stopped rather than being truncated or replaced by an older assertion.

`claim` records the successor role and source-read declarations, changes the actor
atomically, and remains paused. IDs and declarations are audit statements, not
authentication or proof that an actual fresh agent read an image. The real context
replacement and source inspection require campaign/transcript evidence. A correctable
packet omission/version error sends no input and leaves the original handoff eligible
for another explicit request within unchanged limits. Other authority failures stop.

`readmit` is a separate executable request linked to the exact completed claim and
issuance, with one primitive and finite wall/game limits. Its deadline is the minimum
of issuance, claim, ordinary mission allowance and its own cap. Select the original
issued `post_pause_source_id`, even if a separate Observe returned a newer source
after claim; readmission performs its own bounded refresh. If the native binding
matches but that issued source is omitted, the ledger refuses before admission
with the exact required ID and no input. An explicit NEW corrected request remains
subject to all original live handoff, source, Pause and resource guards; this
feedback grants no eligibility or Resume. It freshly observes
and compares complete paused native state under the existing `native_state` rule
for this claimed normal-play Resume, retaining authenticated original/new images.
Incidental pixel changes alone do not require another Claim. Every other native
field, current private-phase/custody/Pause guard and original limit still applies;
missing/corrupt bytes remain fatal. This is no perceptual image equivalence or
recovery/setup exemption. A private Resume-checkpoint journal record links original
and refreshed IDs and the rule without inventing a lease-bound SourceRevalidation.
Readmission bounds the initial Observe command-lock/native wait by that same
deadline (and
the controller's existing15-second ceiling), charges one Resume before publication,
then obtains a fresh successor lease only
from the verified same normal session. Its typed Readmission correlates the claim,
original and refreshed sources and returned charged primitive. It inherits cumulative
costs/time and cannot borrow create/load authority. Unknown Resume retains its charge
and identity; no automatic replay follows. User Pause, controller/native takeover,
close or reopen revoke the private phase. The intake fence refuses competing queued work while a handoff/claim/readmit
handle is unfinished; cached reads/idempotent receipts and independent Pause remain
available. Atomic receipts survive later cancellation;
reopen validates history but restores no phase, process, lease or Resume.

These boundaries have synthetic controller/ledger/archive coverage and actual
clean-context retrieval, image presentation, one-use claim/separate readmission
and useful continuation in the [bounded024 mission](../acceptance/2026-10-21-independent-supply-shelter.md).
That functional evidence proves neither security isolation nor causal memory benefit.

[Contract index](../protocol.md).
