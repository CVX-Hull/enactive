---
owner: lead
status: historical
date: 2026-10-18
scope: Historical activity-distraction repair design and evidence; original pending claims retained
---

Historical repair record. The original pending #120/#100 statements below are preserved in their dated context; both Issues subsequently closed. Current native behavior is defined by the [protocol](../protocol.md) and [native component](../components/native-control.md), not this proposal.


# Cover the ordinary activity-distraction question

[Integrated005](../acceptance/2026-10-18-activity-distraction-stop.md) resumed
without recurring approval and then stopped at a genuinely unsupported prompt.
[#120](https://github.com/CVX-Hull/enactive/issues/120) owns the narrow repair;
#100/#82 remain incomplete. Do not reopen005 or reset any cost, clock or cap.

## Design and reuse

Pinned `game::cancel_activity_or_ignore_query` uses a `query_popup` with category
`CANCEL_ACTIVITY_OR_IGNORE_QUERY`, outside the ordinary player/activity-poll
input scopes in its relevant `do_turn` callers. It differs from the two `query_yn`
sites covered by injected-interrupt recovery. Reuse the existing native
`menu_query` marker around only this query expression. Keep the original
YES/NO/MANAGER/IGNORE bindings and CDDA's cancellation/ignore behavior. Return an
owned string from the lambda so no popup member reference escapes its lifetime.
The marker ends before cancellation, distraction-manager callbacks or redraw.

No global category allowlist, native protocol/schema change, compatibility path,
new dependency or generic recovery framework. Existing exact category, in-game,
empty scope and no-active-query checks apply; nested/unrelated contexts stay
unsupported. Injected owned YESNO recovery keeps its separate authority. The lead
owns this small pinned-source integration; replace/retire it when upstream or
the bridge changes that owner. Mature native UI automation was sufficient for
cleanup, but the ordinary controller needs this explicit boundary to retain its
current input ownership. No broader permission rule solves this support gap.

## Verification and next admission

Patch fixtures check preserved bindings, exact marker lifetime, unrelated waits,
repeatability, upstream hashes and missing/ambiguous anchors. These are source
integration checks, not native classifier or gameplay proofs. Independent review
must inspect the actual pinned caller chain and unchanged guard conditions.
Run the common checks and native build separately. The real graphical lane must
exercise an ordinary distraction question and answer through the supported bridge
without human keys; a missed/unexercised question remains unproven. Do not fake
an activity or change game validation to trigger it.

This implementation brief grants no gameplay authority. A later finite,
prospectively reviewed full-outcome continuation must inherit362whole/337day1/
102lifecycle inputs,4044.464lifecycle seconds,74v3+1archived gameplay unknowns and
two control unknowns, original whole/day clocks and every prior deviation.
Actual remaining time and a complete useful-day forecast govern admission;
development/publication time also counts. Freeze the reviewed source/native at
admission, designate one actor, use stable reviewed CLI commands with actual
permission preflight, and preserve ordinary Pause/takeover. The obsolete005
recorder allowance is retired; no replacement wildcard or per-action approvals.
The existing recorder is historical evidence, not infrastructure to expand.

Keep #120 open until actual native proof, independent review and protected
exact/merged-main publication are verified. No first-day/seven-day acceptance
follows from a successful menu repair.

## Implementation checkpoint

The exact-owner patch passes21 setup tests and a native incremental build on this
Mac. Existing macOS13/minimum linked-library15 warning remains; this is not
other-host support. The corrected common lane passed451 tests plus viewer, diagram,
architecture and governance checks. Independent review found noP1/P2 in the patch,
recorded outcome and affected control. Protected publication and actual graphical
proof remained separate at this checkpoint. Initial governance checks rejected missing provenance fields and absolute local
artifact references in the new historical manifest; metadata and repository-relative
references were corrected without weakening the schema. No repaired prompt had been played at that checkpoint; the later proof is below.

## Real native proof

The [bounded native proof](../acceptance/2026-10-18-activity-distraction.md) verified
prior005save reload and an actual feral-cop distraction with ordinary bridge Yes,
then fresh supported normal play. Independent evidence review found noP1/P2.
22rows/nine new inputs/195.831seconds/157game seconds;371whole346day1/108lifecycle
and4148.431lifecycle seconds,77v3+1archived/control2unknowns remain. Both source
candidate CI runs passed before admission. Final proof Save still needs reload.
Protected final exact/merged-main publication remains before #120 closure; no daily
survival acceptance or automatic campaign resumption.
