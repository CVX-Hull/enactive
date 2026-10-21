---
owner: lead
review_trigger: Popup producer, dismissal policy or ordinary phase ownership changes
status: active
---

# Acknowledge a visible no-choice popup

Independent018 stopped at “You have nothing to consume.” The player explicitly
requested dismissal, but POPUP_WAIT had no QUIT action. It registered
toggle_language_to_en, ANY_INPUT and COORDINATE, with no represented UI rows.
The failed mission, unknown creation ACK, costs and ordered exceptional shutdown
remain retained. No food, usable-water, full mission or normal ending is accepted.
[#139](https://github.com/CVX-Hull/enactive/issues/139) owns the control repair;
[#144](https://github.com/CVX-Hull/enactive/issues/144) owns integrated acceptance.

## Decision and reuse

Use the existing semantic dismissal and key transport. Only rowless POPUP_WAIT
whose actions are exactly ANY_INPUT/COORDINATE after removing the pinned
input_context's ubiquitous toggle_language_to_en gets one SPACE. Registered QUIT
continues to use cancellation. Unknown extra controls, represented choices,
missing signature members and other categories do not authorize this key.

This follows pinned upstream popup.cpp query_once: anykey registers ANY_INPUT
and COORDINATE, while options and cancellation register additional actions.
input_context.h constructors register the language action independently. Native
key_event already encodes SPACE in both keyboard modes. The model chooses the
source-bound dismissal; software performs the deterministic mapping. Exact-image
preflight, authority/Pause, original root/Work/deadline/costs and unknown handling
remain. One delivered key returns partial for effect verification even if the
same or another prompt remains; it never automatically answers again.

This is a small instance of [target-first input](../design/mixed-input.md), not
implementation of its proposed raw mouse API or learned procedures. It fits the
[organic-discovery crosswalk](../design/organic-discovery.md#cross-check-against-prior-work)
and [asynchronous reflection proposal](../design/asynchronous-reflection.md)
without making a critic or the engineering lead approve each key. No new model,
dependency, framework, telemetry protocol or research-performance claim is added.

## Verification and maintenance

ControlIntent, native commands and persisted receipts already support this key;
no field, closed variant or reader changes. Native4/mission8/ledger10/archive3
remain current. No compatibility path or old-run conversion is introduced.
The baseline regression reproduces the refusal. Focused tests cover the actual
producer signature, bare pair, QUIT preference, ambiguous controls/rows, one-input
normal/popup return, unknown non-replay, exact-image dispatch and original
phase/Pause/budget guards. These tests are synthetic, separate from the next
finite native mission. All owned runtime processes are closed before deployment.

Lead owns the coupled policy/current guidance; independent boundary and source
review check producer semantics and failure handling. C-RUNTIME/C-REVIEW and
C-MAINTENANCE revisit this predicate when pinned producer semantics or actual
failures change. No new maintenance schedule is created. Historical failures
stay closed; formal acceptance still requires the complete original mission.
