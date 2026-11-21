---
owner: lead
status: historical
date: '2026-10-24'
scope: Design and development record preserved on this date; current architecture/protocol
  and GitHub own behavior and remaining work
---

# Answer owned distraction questions through the existing semantic control

Independent005 reached ordinary play through the preapproved structured tools,
then stopped at an actual sound interruption. The native boundary correctly
reported `CANCEL_ACTIVITY_OR_IGNORE_QUERY` as a menu with registered `YES`/`NO`,
but interpreted confirmation accepted only `YESNO`. The player sent no answer,
issued Stop and quiesced. Exceptional exact-child teardown is failure custody,
not normal save/exit or successful rest. The original attempt never resumes.

Reuse the current confirmation goal, source-bound question interpretation and
registered native actions for the two known query categories: `YESNO` and the
exact-owner distraction query. Do not admit arbitrary categories merely because
they advertise those action names. The native owner/empty-stack/in-game checks,
current menu boundary, chosen registered action, original phase/source/limits,
Pause and unknown-delivery rules remain. One answer returns fresh evidence and
requires player assessment; it neither completes rest nor automatically retries
an activity. Injected `interrupt_confirmation` retains its separate owner-bound
recovery path. `IGNORE` and `MANAGER` are not added to this binary semantic goal.

The pinned upstream [game implementation](https://github.com/CleverRaven/Cataclysm-DDA/blob/7b2efa5cea38e4d4d97dd0e63b28b9148623da59/src/game.cpp)
cancels on `YES`, leaves the activity uncancelled on `NO`, and gives `IGNORE` and
`MANAGER` distinct behavior. The existing preparation patch surrounds only that
query expression. Native coverage and actions already exist; no engine patch,
native rebuild, new executor, dependency or protocol/persisted-format change is
needed. No unsupported version or former caller path is restored.

The first full common run retained one existing source-reader fixture failure:
operation settlement preceded the writer's final observer publication, which
could republish the fixture's temporarily substituted store. Synchronize that
synthetic transition after final Start publication with bounded events; retain
every original source-binding/negative assertion and production behavior.

Lead owns this small serialized correction and final verification. C-PORTABLE
checks both choices, no repeated input/effect credit, unknown category/boundary,
missing registered action and integration with original activity-root accounting.
C-REVIEW compares fixtures with the pinned producer and retained failure.
C-NATIVE remains the full new independent mission, with fresh-model continuity
and normal ending; passing source fixtures does not accept it. Revisit this
mapping when the native query, semantic confirmation or phase contracts change.
