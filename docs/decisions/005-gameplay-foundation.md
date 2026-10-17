---
owner: lead
status: historical
date: '2026-10-17'
scope: Accepted design decision for future native recovery and bounded gameplay implementation
---

# ADR 005 — Grounded gameplay before model routing

Decision accepted after independent review on 2026-10-17 for #6 and #17. This selects future implementation
interfaces; it does not change current runtime support. The
[review brief](../changes/004-gameplay-foundation.md) defines acceptance.

## Decisions and reasons

First task: a nearby cardinal waypoint and return, with no more than eight movement
primitives. Two verified stages exercise planning, skills, evidence retention and
correction using existing visible observations. Water collection and general survival
need unsupported inventory/safety evidence; a single keypress does not exercise the
feedback architecture. The [gameplay contract](../design/gameplay.md) defines the exact
completion predicate, records and budgets. One capable planner is sufficient for
this first experiment; model tiers remain evidence-gated in #25.

Native control: positively distinguish normal play, activity polling and prompts.
Preserve Pause and add explicit operator recovery through existing engine input and
confirmation semantics. Do not directly mutate/cancel activities or broaden arbitrary
keypress admission. A narrow recovery inbox can operate while gameplay is unresolved;
it remains inside the existing single controller/game-thread authority. Native wire
v2 is a coordinated producer/consumer change. The [native design](../design/native-control.md)
defines eligibility, identity, unknown outcomes and deliberately unsupported cases.

Keep the existing controller as the authority boundary and implement only the small
domain-specific supervisor around it. Reuse its atomic transport, locks, freshness,
guards and reconciliation, plus existing JSON Schema tooling for serialization.
Do not build a generic state-machine, behavior-tree, workflow or agent framework.
No library or provider is installed/selected by this design publication.

## Reuse assessment, verified 2026-10-17

This is a source/documentation comparison, not an executable performance comparison.
The lead checked release API timestamps, tagged metadata/licenses and the documented
semantics below. Moving documentation must be rechecked at adoption; snapshots and
hashes are retained in the local design-round evidence directory.

| Option | Evidence and fit | Decision / maintenance cost |
| --- | --- | --- |
| Existing controller + small typed supervisor | Local controller already owns at-most-once dispatch, pause, unknown outcomes and guarded walks. New domain records are needed under any option. | Selected for two stages and one skill. Keep transitions explicit and test adversarial events; do not grow a general engine. |
| [py_trees 2.6.0](https://github.com/splintered-reality/py_trees/releases/tag/2.6.0), released 2026-09-10 | [Composites](https://py-trees.readthedocs.io/en/devel/composites.html) and [lifecycle](https://py-trees.readthedocs.io/en/devel/behaviours.html): useful reactive composition and inspection; memory sequences can skip prior checks. Parallel composites tick sequentially; INVALID is a lifecycle signal, not native cancellation. | Defer. Its four statuses need our separate partial/unknown evidence records anyway. Never put authority guards only in a remembered branch. [Tagged metadata](https://github.com/splintered-reality/py_trees/blob/2.6.0/pyproject.toml) declares pydot and BSD-3-Clause; Python minimum is commented out, not a packaging guarantee. Release line adds 3.14 support; local compatibility still needs tests. |
| [transitions 0.9.3](https://github.com/pytransitions/transitions/releases/tag/0.9.3), released **2025-07-02** | [Tagged README](https://github.com/pytransitions/transitions/blob/0.9.3/README.md): queued/conditional transitions, LockedMachine and AsyncMachine. Locks cover machine methods, not arbitrary model writes; queued trigger return is not eventual execution success. | Defer; closest alternative if lifecycle composition expands. [Tagged setup](https://github.com/pytransitions/transitions/blob/0.9.3/setup.py) requires six; graph tools are optional. MIT. Our Python 3.14.7 runtime is not established compatible by this source review. Master 0.9.4 text is not a verified release. |
| [CodeHack](https://github.com/BartekCupial/codehack/tree/1a3024fac1e67e9264deadbf00384aa5a37718bb) | MIT repository linked by the [authors](https://bartekcupial.github.io/abstraction-ladder/); [paper v1](https://arxiv.org/html/2609.31076v1), 2026-09-25, supplies game-skill evidence. README requires Gymnasium/NLE/MiniHack and a platform-matched wheel. | Use as an interface/experiment reference. No imported code or game-state adapter: NetHack actions and observations do not satisfy our CDDA visibility/authority contract. No published release or CDDA compatibility evidence was established. |

BSD-3-Clause and MIT are permissive licenses, but adopting code still requires notice
retention and dependency pinning under S-DELIVERY. This assessment does not change the
licenses of CDDA-derived integration or assets. Tagged license texts were read.

## Reversal and maintenance

Revisit transitions when state handling acquires duplicated transition machinery or
hierarchical/queued lifecycle needs; revisit py_trees when independent reactive skills
need inspectable composition. Compare a representative implementation against the same
pause, stale-intent, partial/unknown and budget tests. Adopt only if it simplifies
review and maintenance without weakening those invariants. Measure setup burden and
debugging cost, not only lines removed. If custom work starts resembling a framework,
stop and reopen this decision before expanding it.

Keep records independent of either library's status enum so replacement is local.
Revert native releases as a matched producer/consumer set, never a mixed wire version.
If the activity/query hooks cannot prove scope ownership, reject the unsupported case
and revise the design; do not bypass the engine to make a demonstration pass.

Research review #26 covers consequential new findings and weekly active-design
currency; #13 covers control/tool maintenance. Successful native probes and later
whole-trajectory model comparisons, not this ADR or a new paper alone, justify claims
about runtime reliability and tier efficiency.
