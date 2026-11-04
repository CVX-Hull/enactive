---
owner: lead
status: historical
date: '2026-11-03'
scope: Owner decision on the ADR-007 first slice after the offline comparison screen; no runtime qualification
---

# ADR 007 first-slice outcome

On 3 November 2026 the owner approved retaining the current player and recording
that decision on main. **V4 benefit remains unestablished.** The planned
claim-deciding comparison did not run. The original
[decision plan](../decisions/007-player-subgoal-level.md) required a worthwhile
gain over the player keeping its own ledger, within cadence and accepted cost.
Production source at the decision was `bd337d88604ccd079d7f09850cf32f45374da323`.
Its [computer-control contract](../contracts/computer-control.md) governs play.
Draft [PR #332](https://github.com/CVX-Hull/enactive/pull/332) preserves the
v4 candidate at `3d1dc0445a8955e5d6eb46adbed3c027152b9024`. The supersession map
was conditional on adoption and did not take effect.

## Why the comparison stopped

The four-arm v4 retained-progress count screen reached 48.7% detection at best
in the tested 1.4× scenario, against the required 80%. The recorder draft that
fit allocated $162.69 of $165.95 in conservative remaining headroom, with
roughly 80% or 25% simulated passage under different
usable-return assumptions, before stage stops and incomplete scoring. Recorder
qualification would still leave the gameplay comparison unresolved.
[Original rescope and retained evidence](https://github.com/CVX-Hull/enactive/issues/329).

The simpler design proposed one bounded lookup of earlier screenshots and
actions alongside the same player's ledger. Candidate-only R7 supplied a concrete access
gap: two delivered screenshots of the same map were byte-identical and absent
from its player store. This one development session establishes neither
later-session use nor gameplay benefit. It met R7's own clean-native-exit
exception. Its original receipt remained incomplete with final delivery unknown.

In the scenario of one additional visible retained change per four later sessions, the best
screened allocation with reserve reached 53.10% detection with complete
evidence, and 7.47% with optimistic modeled session and audit completion. Those maxima
come from possibly different cells. Rates, costs and missingness were
assumptions informed by limited development data, not measured probabilities
for this study. A larger gain could pass the complete-evidence screen in an
optimistic scenario. Independent review also found that the proposed
randomization test's exact guarantee applies to no effect on any lineage.
It can overstate confidence in average benefit when some lineages improve and
others worsen. The available design therefore fell short of a credible
claim-deciding run.
[Reviewed offline design, calculations and review](https://github.com/CVX-Hull/enactive/issues/329#issuecomment-6621391952).

## Evidence preserved

- [#352's original replay](https://github.com/CVX-Hull/enactive/issues/329#issuecomment-6572161040)
  failed G3 and G5. The replay and its thresholds retain their original disposition.
- [#345](https://github.com/CVX-Hull/enactive/issues/345) passed its recorded
  point-estimate agreement rule at 0.673, with a lower bound of 0.56. That did
  not establish the proposed fresh lower-bound gate of 0.60. The 43 inventory
  entries count calls across versions. The closure replay covered the 21
  committed v3/persistent Work records. The rest remain outside that replay.
- [R7 scoring](https://github.com/CVX-Hull/enactive/issues/329#issuecomment-6620623980)
  stopped on an unsettled request. A separate
  [60-second feasibility check](https://github.com/CVX-Hull/enactive/issues/329#issuecomment-6620761275)
  finished two paired packets and still found directional disagreement on
  the player-condition claim. Both are development evidence. Keep the failures,
  frozen protocols, missingness, and holdout exclusions.
- The last #329 accounting checkpoint retained $78.739547275 in recorded item
  spend and $5.314596385 in uncertainty against the $250 ceiling. This decision
  and its closeout add $0 in model or gameplay spend. The candidate and original
  ledgers are preserved. The separate [#347](https://github.com/CVX-Hull/enactive/issues/347)
  pilot retains its revise outcome and distinct cap.

The offline package and large evidence remain local at
`.runtime/iteration329/history-comparison-2026-11-03/`. Its manifest SHA-256
is `f7bbbadcd0f6bd8f9722fbf2a62a99c971cec00df12e810f75a161483c379f77`.
The linked #329 record retains the reviewed analysis, limitations and input
references. This editorial record establishes the decision and its provenance.
It adds no native, gameplay, cadence, learning, or portability qualification.

## Follow-through

The [#326 outcome](https://github.com/CVX-Hull/enactive/issues/326) is the decision
to retain the current player. [#136](https://github.com/CVX-Hull/enactive/issues/136)
still owns broader independent play. [#164](https://github.com/CVX-Hull/enactive/issues/164)
still needs its useful-decision cohort. [#177](https://github.com/CVX-Hull/enactive/issues/177)
retains the authentic reuse trigger. [#42](https://github.com/CVX-Hull/enactive/issues/42)
retains the read-only evaluation question and needs a supported producer of
expectation evidence.

The closeout disposition for [#178](https://github.com/CVX-Hull/enactive/issues/178)
was optional, deferred reflection. A future reshape would start with the
current player's ledger and a concrete case where it could not recover prior,
relevant evidence. A saved note that is hard to find and an observation the
player never saved pose distinct questions. A single read-only lookup would
warrant comparison if the gap is repeated and review supports credible audit
completion, costs and at least 80% detection for a worthwhile visible gain.
A separate adviser would need evidence of a distinct failure the simpler
access path cannot address. Existing stops and owner-held decisions still
govern changes to contracts, protocols and spend.
