---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Explicit operator recovery

`Controller.recover(kind, **payload)` is the local Python operator interface.
Authenticated loopback `POST /api/recovery`, explicit CLI recovery commands and
the spectator recovery panel expose this same operator-only boundary. Ordinary
`/api/command` and planner execution reject recovery kinds.
Recovery first pauses and revokes gameplay, then admits its own durable token.
The process lock outlives both writers; a nonblocking control lock prevents two
recoveries. Recovery never waits for the ordinary command lock. The data lock
serializes admission and revocation; shutdown revokes and waits for both writers.

Files are `control.json → control-claimed.json → control-response.json`, with
separate UUIDs, bounded native duplicate ledger and `control-admissions/` records.
An envelope has exactly `protocol: 4`, `id`, `kind`, `session`,
`control_generation`, `authority`, `created_ms`, `deadline_ms`, plus the operation's
fields below. Integer Unix-millisecond expiry is exactly creation plus 2000;
future creation has at most 1000 ms tolerance. Maximum request size is 4096 bytes.
No deadline extension, implicit refresh or automatic retry is permitted.

| Kind | Additional wire fields | Eligibility and delivery |
| --- | --- | --- |
| `request_interrupt` | None | Eligible activity poll advertises it; resolve registered native `pause`, preserving the engine's keyboard-interruption policy |
| `answer_interrupt` | `boundary_id`, `revision`, `frame`, `interrupt_request_id`, `choice` (`YES`/`NO`) | Exact owned rendered query; resolve that choice's active usable binding |
| `continue_debug_once` | `boundary_id`, `revision`, `frame` | Exact raw debug prompt; deliver one Space, never ignore future errors |

Python and HTTP callers supply `expected_session` and `expected_control_generation`.
Answers/dismissals also require `expected_boundary_id`, `expected_revision` and
`expected_frame`; answers add the owning `interrupt_request_id` and `choice`.
HTTP requests use exactly `kind` and the required fields above, with optional
positive `timeout` up to 15 seconds. They retain the ordinary endpoint’s Host,
origin, token, content-type and 4096-byte guards. Malformed input returns 400;
rejected/unknown/controller-error outcomes return 409; other terminal recovery
outcomes return 200. HTTP success reports delivery semantics only. The CLI uses
`--session`, `--generation`, and for prompt operations `--boundary`, `--revision`,
`--frame`; answers also require `--interrupt-request-id` and `--choice YES|NO`.
No surface fetches new authority to silently replace an operator’s decision.

The controller checks freshness and advertised operations. Native rechecks session,
generation, eligibility and rendered prompt evidence, then reads the host token
again at the final commit gate. Delivery latches Pause and increments native
control generation/revision. A later Pause cannot undo already committed input.

Only the specific cancellation questions invoked by harness-delivered native
pause gain interruption ownership. Generic YESNO questions do not. Nested unrelated
input or debug overrides that scope. Each owned question gets a new boundary ID;
returning from a nested boundary requires new matching evidence. Scene metadata
remains exclusive to normal play. Recovery is polled before ordinary requests,
even while an ordinary response is pending, after native input and Pause handling.

A control response has exactly `protocol`, `id`, `status`, `error`, `state`; `state`
is the ordinary current-v5 observation shape. `dispatched` is nonterminal.
`prompt_opened` requires an actual fresh owned confirmation frame.
`answer_delivered` and `dismissal_delivered` report input delivery, even if no new
successful frame is available. `not_applicable` and `rejected` report no applicable
operation or a failed gate. Host timeout is `unknown`; host failures are
`controller_error`. No status alone proves cancellation, error repair or task success.
Transport-only Pause preserves scene revision so recovery can validate the rendered
activity frame that informed admission. Actual input, takeover, resume and boundary
changes still invalidate authority. An activity can finish or reach an unrelated
prompt before claim; inspect the result and observe deliberately, without automatic
refresh or retry. [Native acceptance](../acceptance/2026-10-17-native-recovery-planner.md)
separates production gameplay from injected timing and reply-loss probes.

The original gameplay response/pending identity is preserved. Control results may
update passive state but cannot resume gameplay. `control_pending` and
`control_unknown_outcomes` expose separate uncertainty; durable admissions outlive
bounded display history. A matching terminal result can retire only its own
admission. After timeout, only an explicit successful fresh observe after the
native deadline may reconcile the live control slot; passive status cannot rearm
it. Revoke, retire unclaimed work and reject unreconciled claims/active writers
before deliberately admitting another recovery. Keep historical unknown outcomes
and their admissions; reconciliation does not infer what happened or replay input.

Offline migration can preserve older unknown actions through
`historical-incidents.json`: exact `schema: "incident/1"`, `incidents` (at most256
references and128KiB for the ASCII-escaped JSON list). The aggregate bound leaves
room for startup/status duplication within the existing client response budget.
Each record has `id` (1–128 chars), `channel` (`gameplay`/`control`), `source_path`
(project-relative under `.runtime/incidents/`, at most 1024 chars), `source_sha256`
(lowercase SHA-256) and `reason` (1–1024 chars). IDs are unique per channel. Startup
verifies containment, file existence, at most 1 MiB and hash, without parsing old
bytes. Invalid references block startup. These surface as `historical_unknowns`
and journal evidence, granting no authority, replay or inferred resolution.

[Contract index](../protocol.md).
