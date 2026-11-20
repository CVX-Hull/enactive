---
owner: lead
status: historical
date: '2026-11-19'
kind: run
scope: 'One fresh Campground world, a same-session handoff, a named reload and an early resource choice'
---

# Joanna Campground opening, handoff and resource choice (#803)

## At a glance

Morgan Reed reached the assigned campground, used a matchbox found there to
light a cooking fire, slept naturally and resumed useful work. The first
eligible choice used a five-minute-old observation. The survivor’s name was
absent from the fire’s effect window. The named reload verified the saved
checkpoint, then stopped on a provider refusal before another Save. At the
last visible clock even the earliest world observation was 36 minutes and
two seconds short of the delayed window. The study supplies an ordinary-access
control and an observed handoff. Memory advantage remains unmeasured.

## The revised opening and the real handoff

The owner approved one fresh world with optional serial reloads on the pinned
OpenAI Standard Terra route, ordinary knowledge and full context. The approved
initial inventory SHA-256 was `a5f1decb78a51d2c77948e39d9f23e6e15b5efe15243b527107e3bd12af9c82c`.
Both admissions used source `236e532a393df1e68227dd12ddcfc9b982012559`.
The opening session was `8a4badef08b94ed78a8a031bf6751354`, the reload
`747a4e62780740e9bab2e83a12d3d466`. Source numbers below are suffixes
within their admission. [First-decision review](2026-11-19-fresh-start-decision-800.md) · [Owner decision](../decisions/owner-decisions.md)

| Decision | Returned evidence |
| --- | --- |
| Enter the assigned editor | Opening source 2 shows Preset Character highlighted. The player moved Up, observed Custom Character selected in 3, and separately confirmed it. Source 4 showed the default rules and world Joanna. Sources 234 and 237 showed Wilderness, Survivor, Campground and the name Morgan Reed. Source 238 was a separate finish prompt. Sources 292 and 312 established the campground at 08:00 on spring day 61 and the living survivor’s name. |
| Continue an existing session | Actor 001 request 210 sealed context `f967fcc5e13d49ee9f9471c7598c7ecf`. Actor 002 received the same base mission and the labelled predecessor report. Its first request observed the same item list, source 10424. Its next input returned a new campground overmap, source 10426. The successor continued the live game. Neither handoff frame displayed the name or clock. |
| Resume a saved survivor | Opening sources 22032 and 22037 showed Morgan Reed and the worn filthy sweatshirt. Source 22039 showed the ordinary Save confirmation at 07:13:38 on spring day 62. Source 22125 showed Joanna (1) at title and 22126 showed the separate Quit prompt. The final Quit delivery stayed unknown after collection on its original ID. The native process independently exited zero without forced signals. Reload sources 2 and 3 showed Joanna and the named survivor. Sources 184, 204 and 206 verified the saved clock, Morgan Reed and the worn sweatshirt before substantive play. |

These observations establish one successful opening, in-session continuation
and named Load under the approved procedure. They do not establish that the new
wording caused the difference from #799.

## First eligible resource choice

A chronological reader screened the travel interruption at opening request 43.
The prior tool was visible, but the immediate search did not present a concrete
resource choice. The reader also recorded the full tin and unmet recipe
requirements before request 62. The first qualifying cutoff was actor 001
request 88, through the fetch at line 1184 of its original host trace. The
reader stopped there, before the answer, target lookup or action. The sealed
prefix SHA-256 was `b27892f2bda45e1ff2584c11e47d5c917f79e1a2c1e8ba073e1a6d04c5728606`.

- **Before.** The matchbox found on the campground groundsheet in source 394
  was acquired at 08:00 in 396. Source 1441 showed it alongside a full matchbook.
  After crafting, relocation and gathering food, source 2821 showed 08:05.
  Recipe 2874 showed sufficient cooking quality and uncooked food, with nearby
  fire still required. The actual request included the clock, recipe, earlier
  pickup intent and ordinary source handles. The old matchbox, two-tool
  inventory and brazier images were omitted. An inventory inspection was
  available. Attention and lookup success remained unknown to the before reader.
- **Effect.** A separate reader saw the executed project from request 88 onward.
  Source 3377 showed wood on the fire ring. The ordinary item menu in 3415
  showed nine matches in the matchbox and twenty in the matchbook. Source 3805
  showed successful ignition and a visible flame at 08:10:58. Later source
  4493 distinguished the used item by its changed count of eight, with twenty
  still in the matchbook. The survivor was alive, but no name appeared at
  ignition or in the next five completed visible operations. The cooking project
  reached 3% before the player switched to heating water. Its later work and
  the later visible hot water were separate outcomes.

The effect establishes actual use of the previously found resource. The ordinary
item menu exposed both alternatives before use. The study supplied no comparison
arm and no independently named effect within the frozen window.
[Study procedure #803](https://github.com/CVX-Hull/enactive/issues/803) · [Lookup follow-up #804](https://github.com/CVX-Hull/enactive/issues/804)

## Natural wake, cutoff and provider stop

Opening source 17496 showed twelve portions of boiled clean water in a jar.
Morgan slept in the closed tent. Source 20858 showed a natural wake at
07:02:40 on spring day 62. The player then salvaged and wore a sweatshirt,
cooked two hot dogs and ate them. In the reload, source 606 showed a finished
four-hot-dog batch on the ground. Sources 637 and 668 still showed 07:23:58.
Pickup and consumption of that batch were unverified. The lineage had one
natural wake, useful work after waking and no qualifying 24–48-hour-old fact.

During the opening, actor 002 request 211 received HTTP 429, waited for the
indicated delay and succeeded on request 212 with the same payload. In the
reload, request 32 received HTTP 502 about 34 seconds into its 60-second
request deadline. The response requested a 60-second delay. The host marked
the refusal eligible, then the original timer fired during backoff. There was
no second fetch for this refusal, completed tool call, new named Save or
normal exit. Neither event exercised partial HTTP 200 stream recovery.
The remaining reloads were ineligible and unused authority expired.
[Backoff review #805](https://github.com/CVX-Hull/enactive/issues/805)

## Accounting and custody

The [run ledger](../../data/evaluation/runs.jsonl) records each provider
subtotal and the unpriced attempts separately. The [metrics snapshot](../../data/evaluation/run-metrics.jsonl)
contains both evaluated admissions. The evaluator’s automatic identity field
remained unknown at the boundary. The named Load was independently read from
the returned screens.

Both supervisors verified closure. The lead found all owned process groups
absent, the listeners closed and the shared game lock idle after each admission.
The maintained restore operation returned all 82 original userdir files with
matching hashes. The [evidence index](../../data/evidence/index.json) locates
the admission packages, conditional checkpoint archive, working ledger, approval,
disjoint reader records, evaluator and closed study userdir. The displaced
original recovery archive remains available. After verifying every hash, the lead
retired the duplicate admission directories, operator directory, configuration
archive, conditional checkpoint archive and closed study-userdir archive.
