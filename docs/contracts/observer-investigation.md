---
owner: harness maintainer
review_trigger: Selected export, import schema or resource boundary changes
status: active
---

# Recorded investigation artifact

The passive observer owns `observer-investigation/1`. Its producer, shared worker,
reader, tests and documentation ship together.
Unknown versions/fields reject. Native/player formats remain current and unchanged.

`tools.evaluate investigation-export SELECTION.json --output BUNDLE.json --html READER.html`
reads one explicit `investigation-selection/1` file. It names 1–4 cases with
`id`, `title`, `directory`, optional `observer_exports`, optional `source_ids`,
and optional `assessments`. Relative input paths resolve against the selection
file. These private paths never enter the exported artifact. No recursive sibling
discovery or live-case export. A case requires a current `campaign-receipt/2` with
actual `deciding_hosts_quiescent`, `native_absence_verified` and
`input_authority_revoked` true. Outcome can be failed/incomplete. Existing analyzers
validate the current computer-session/host/observer versions; unsupported evidence
is a gap or explicit rejection, never a synthetic replacement.

The closed JSON root contains only `schema` and `cases`. Each case has:

| Field | Definition |
| --- | --- |
| `id`, `title`, `session`, `source_commit` | Bounded public identity, original opaque session and source revision. Case IDs are distinct ASCII `[A-Za-z0-9][A-Za-z0-9._-]{0,79}`. |
| `configuration` | Array of at most two actor-scoped objects: `actor_id`, `model`, `provider`, `api`, `effort`, `requested_service_tier`, `provider_only`, `provider_order`, `allow_fallbacks`; missing values null. Provider lists contain at most 32 identity strings; missing lists are null. No bearer/key/base URL/raw settings. |
| `coverage` | `event_candidates`, `event_retained`, `event_omitted`, `source_candidates`, `source_retained`, `source_omitted`, `observer_status`, `invalid_clocks`, `notes`. Counts refer to this selected export; notes disclose omitted fields/rows/missing measurements. |
| `events` | At most 2,000 complete allowlisted rows defined below; no raw request/result/argument objects. |
| `sources` | Explicitly selected original image entries defined below. Other original source IDs remain referenced but unavailable in the bundle. |
| `assessments` | At most 16 explicitly selected existing-review/player-claim notes: `label`, `text`, `attribution`, `reference`, `evidence_ids`. Reference is inert text to a public tracked report, never an automatic URL or local-file read. No new annotation store/editor. |
| `accounting` | Object containing nullable known `attempts`, `host_seconds`, `configured_estimate_usd`, `missing_usage_attempts`, `conservative_reservation_usd`; label estimates/reservations, never invoice. |

Every event has `id`, `kind`, `label`, `text`, `text_omitted_chars`, `original_omitted_bytes`, `actor_id`,
`request_id`, `tool_call_id`, `operation_id`, `program_id`, `run_id`, `native_id`, `source_id`,
`start_wall_ms`, `end_wall_ms`, `clock`, `elapsed_ms`, `disposition`, `links`,
and `metrics`; absent scalar evidence is null (text can be empty). `kind` is
`request`, `tool`, `program`, `operation`, `native`, `source`, `statement` or
`observer`. IDs are case-unique and preserve original IDs in named fields; host
IDs include the original actor directory. `links` contains only explicit related
event IDs, never inferred causality. Dangling omitted links remain disclosed.
`run_id` retains the original program issuance separately from its program version;
`native_id` retains the original native exchange separately from its operation.
Group program executions by the actual run ID, never by program version alone.
Known creation/presentation/statement/result instants render as timestamp points,
not zero-duration work; incomplete request intervals remain unplotted. Wall times
support an approximate shared-axis view; `elapsed_ms` retains original
same-domain durations. Invalid/missing clocks do not become zero or plotted spans.
`clock` identifies the original domain/assumption; do not subtract actor epochs.

`metrics` has only optional nullable numeric `input_tokens`, `output_tokens`,
`reasoning_tokens`, `cache_read_tokens`, `cache_write_tokens`, `payload_bytes`,
`text_bytes`, `image_bytes`, `image_parts`, `projection_ms`, `first_body_ms`,
`first_content_ms`, `first_tool_argument_ms`, `headers_ms`. Timing metric names
retain analyzer definitions (fetch-relative durations, not epoch timestamps).
Counts/durations are finite/nonnegative. Reasoning counts are not reasoning text;
subset counts are never added twice to totals. No semantic diagnosis/quality score.

Source entries have `source_id`, nullable nonnegative integer `capture_id`, `presented_ms`, `received_wall_ms`,
`sha256`, `width`, `height`, `png_base64`, `unavailable_reason`. Available entries
retain exact original bytes, PNG geometry and digest; absent/corrupt/oversized
sources have null bytes and an explicit reason. Source IDs are case-local; selectors
never substitute latest pixels. Integrity checks establish internal consistency,
not trusted authorship of an imported bundle.

String limits: identities 256 characters, labels/titles 240, public event text
4,000, reason/clock/reference/coverage note 1,000, assessment text 4,000; at most
32 coverage notes, 64 links/event and 64 evidence IDs/assessment. Original narration `omitted_bytes` stays separately reported in
`original_omitted_bytes` (null when unknown); no bytes-to-characters conversion.
`text_omitted_chars` counts only additional export truncation of retained text.
String character bounds use Unicode code points. Unexpected nested values reject;
allowlisted data is copied field by field. No private reasoning, prompts/raw
arguments, secrets or unrestricted paths. Actor configuration is selected, not
an arbitrary dictionary echo. Selected review notes are fallible attributed data.

The whole encoded JSON is at most 16 MiB, with at most 16 selected PNG entries
across all cases, and at most 50 rendered event rows/page. Before browser decode,
verify the static PNG header geometry/digest and reject multi-frame images or
images above 64 MiB RGBA pixels.
Keep at most two visible image decodes concurrently within a combined 64 MiB
decoded budget; a one-image inspector fits this bound. Cancellation/selection
change releases owned URLs; an 8-second decode watchdog reports unavailable while
retaining the reservation until the platform promise settles. Missing/oversized/malformed images stay
unavailable. No full image history is loaded into the DOM.

The [observer component](../components/observer-operations.md) owns navigation and
failure behavior; [evaluation](../evaluation.md#investigate-a-selected-interval) owns
interpretation, and [start/observe](../operations/start-observe.md) owns the procedure.
