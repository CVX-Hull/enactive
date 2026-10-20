---
owner: lead
status: historical
date: 2026-10-20
scope: Coordinated mission ingress, historical observer and continuity reducer source qualification; no game launch or mission admission
---

# One mission ingress and historical memory observer

The candidate removes the live waypoint runtime, `/api/gameplay` and `gameplay-*`
CLI. One MissionRuntime accepts strict mission/2 through `/api/mission` and
`mission-request --request` with a bounded regular JSON file directly under project
`.runtime/mission-requests/`. Unsupported old contracts/commands reject. Passive
waypoint libraries remain study components, without another live execution path.
Current operation belongs to [protocol](../protocol.md#integrated-mission-lifecycle)
and [architecture](../architecture.md), not this dated report.

## Verified scope

- Raw HTTP commands cannot race admission: Start excludes unsettled raw requests;
  a pending Start rejects raw entry. A short lock/counter leaves ordinary and
  recovery channel waits independent. Original HTTP entry generation prevents a
  stale Resume from crossing Pause. Cached status and Pause bypass admission waits.
- Production Start/Observe remain read-only and cannot adopt an unrelated already
  unpaused normal scene, acquire its lease, ingest its facts or seed mission time.
  Core skill-composition tests explicitly mock the identity boundary; they do not
  qualify owned launch, creation or loading. No bypass flag is exposed.
- Interpreted cancellation delivers one registered QUIT, or TEXT.QUIT for a string
  editor, under the existing owned phase/source/budget checks. The result is partial
  for verification. It neither aliases NO nor answers a subsequent question.
- Status caches the exact last journaled context packet. Claims, Work, sources,
  omissions and dispositions stay historical as of that packet, including after
  later observations/corrections. Rendering neither retrieves memory nor sends input.
- The observer uses typed mission Observe and locks raw input/Resume/recovery for
  nonterminal or malformed mission state. Pause remains available. Model calls,
  tokens, external inference time/cost and intervention counts remain unknown when
  unmeasured; primitive counts are not model decisions.
- The timeline reducer requires canonical chronological normal-session endpoints,
  equal turns and valid retained sources before summing across sessions. Disputes,
  loss, regressions and invented links reject. Runtime has no lifecycle producer
  yet; unexplained session change therefore makes cost unknown, without reanchoring.
- Failed HTTP bind creates no mission worker; failed metadata publication closes
  the bound socket and worker. No global process/configuration changes were made.

## Checks and review

`tools/check.py` passed 802 Python tests, viewer regressions, Python/JavaScript
syntax, Ruff, four Import Linter contracts, local document links/stewardship,
governance and the pinned diagram render/receipt checks. The total reflects removed
retired-executor tests and added current contract/core/HTTP/timeline coverage; it
is not comparable reliability or model efficacy. Independent reviewers cleared
source admission/Pause/recovery boundaries, observer behavior, timeline endpoints
and cancellation/cache semantics. A stale live-waypoint design reference found
in review was marked as the historical first-slice design with current links.

A local pinned-browser layout fixture at 1100×850 showed no horizontal page
overflow, usable Pause, disabled raw Resume and enabled mission Observe. Expanding
memory retained its historical packet wording. Rendering issued no POST and had
no browser script error. The screenshot itself labels this as a layout fixture;
its reused historical menu PNG and synthetic state are not native gameplay proof.
Updated player/ownership diagrams were rendered and visually inspected separately
for readable responsibility and feedback paths.

The installed Codex policy checker parsed the project-only rule and its inline
cases: current mission-request matched allow; retired gameplay-request had no
match. The rule does not pin source or grant mission authority. Actual-player
loading and absence of recurring review require passive preflight for this changed
entry point; no reload/activation claim follows from source matching.

## Retained failures and remaining gates

An early broad admission mutex blocked independent recovery. The existing
regression caught it; the short lock/counter correction passed that regression
and both ordered admission/Pause races. An initial HTTP navigation fixture aimed
at an unsurveyed diagonal; it stopped unknown. The fixture was changed to observe
its intermediate cardinal route, without weakening map eligibility. A layout
helper initially parsed the test fixture incorrectly; the helper was corrected.
These are development failures, not native/model performance measurements.

No game, deciding mission or new normal-play session was launched. Owned lifecycle,
identity/adoption, actual editor/item/activity behavior, exact same-character
save/process restart/reload, real fresh player-context retrieval and final normal
shutdown remain required. This report accepts neither #144's mission nor #145's
seven-day readiness. The [wire4 menu-only probe](2026-10-20-native-presentation.md)
retains its separate scope and unknown final acknowledgment. The
[first campaign](2026-10-19-seven-day-survival.md) remains supervised development data.
