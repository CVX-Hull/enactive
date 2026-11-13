---
owner: lead
status: historical
kind: decision
date: '2026-11-13'
scope: 'The owner''s premise on long-term memory and fourteen owner decisions of 13 November 2026 on the memory direction, the memory screen, the curator''s failed-request charge, the responsiveness criterion, the route, the context, the smaller model, text budgets, the timing reader, the replay probe and the spend limit''s real check (#445, #442, #164, #25, #441, #556, #555)'
---

# Memory and cadence decisions, 13 November 2026

Two design notes were written, independently reviewed and merged on 13 November 2026:
[memory for long-horizon play](../design/long-horizon-memory.md) (#588, #589) and the
[cadence plan](../design/cadence-plan.md) (#587). Their owner decisions were put to the
owner through the question tool. Each answer is quoted. Nothing was spent, no study
was started and no run was made.

## The premise

Stated by the owner in the session goal and recorded on
[#441](https://github.com/CVX-Hull/enactive/issues/441#issuecomment-6854313488) and #145:

> CDDA is not a short-memory decision problem. What matters now was often seen days
> earlier, so the player needs working long-term memory. Memory is settled before any
> seven-day or other long run; the seven-day screen stays parked.

## Memory

| Question | Owner's answer | What it settles |
| --- | --- | --- |
| Which direction the player's long-term memory takes | "Let's keep the dedicated curator. In the long run the actor model might be replaced with a small one to achieve fast performance, and curator will be the main driver of long term intelligence in general. Writing notes also takes latency. Let's also look into a better prompt/context setup than our current setup." | The curator stays the writer of the store, as in decision D1 of [ADR 009](../decisions/009-curated-player.md). The lead's recommendation to deliver the player's own notes first is not taken. How stored knowledge reaches the playing model, and how its prompt and context are built, is to be redesigned |
| What is prepared next for the memory experiment | "Free checks and protocol" | At \$0: an audit of what the player did after each recorded memory query, a replay of the three stored losses against the proposed delivery, and a written protocol for a live screen with its threshold and a simulation that the measure can detect an effect. Running the screen is a separate approval |
| Whether a copy of a sealed saved game may be continued, one game at a time | "Allow a sequential copy" | The screen may start from a copy of the held-out lineage's saved game (#522). The sealed original is untouched. Using it ends that lineage's held-out standing |
| How the curator charges a request that fails with no cost reported (#556) | "Zero for early errors" | A request the provider refused before generating counts at zero. The lead had recommended a fixed bound. It is changed when curator sessions next run |

## Cadence

| Question | Owner's answer | What it settles |
| --- | --- | --- |
| What happens to the 2 s responsiveness criterion (#164) | "The real time requirement is our aspiration, but we also have to respect technical limitations now and prioritize on getting it to work and successfully play first." | The criterion stays as the aim and does not gate present work. Successful play comes first |
| Whether the route changes now or after memory | "Memory first" | Route changes wait until the memory and context design is settled |
| The route for development runs until then | "Keep the current route" | The current model at medium effort on the default tier |
| Whether a small context is the first lever on speed | "Yes, designed with memory" | A bounded context is the first speed lever, and its form is chosen with the memory and context design, on a measurement |
| A smaller model as the playing model (#25) | "Defer as player, keep for roles" | The playing model is not switched now. #25 stays the place where small models are tried in narrower roles and, later, as the playing model |
| Against what responsiveness is judged | "The complete player" | #164 is judged on the full design, with program steps measured there |
| Whether added prompt text is capped before it is measured | "I don't think we should have hard cap unless experience shown that it's necessary, so that we don't get in the way of the models." | No hard cap on knowledge updates or intent text. Their cost is measured in the first run that has them; a cap is added only if that shows a need |
| Whether the response-time script becomes a tracked tool | "Track and extend it" | It becomes a tracked reader of sealed traces and is run on the other sealed lineages, at \$0 |
| When the paid replay probe runs | "After memory and context" | Not now. It needs a fresh approval then |

## The spend limit's real check

The lead first proposed a real run with a \$0.10 limit, which the owner approved
("Approve, max \$0.25"). That run could not be packaged: a package's finish reserve
must be at least one request's bound, \$0.4096 on the current route. Asked again with
that stated, the owner answered "Leave it to tests". The approval was not used. The
decision is also on [#555](https://github.com/CVX-Hull/enactive/issues/555#issuecomment-6854444281).

## What follows

- **The memory screen's arms change.** The memory note proposed comparing the current
  player with delivery of the player's own records. Under the owner's answer the
  comparison is the current player against a curator-written store delivered through
  the redesigned context. The protocol states the arms.
- **Three pieces of work are opened**, each at \$0: the free checks and protocol
  ([#590](https://github.com/CVX-Hull/enactive/issues/590)), the context design
  ([#591](https://github.com/CVX-Hull/enactive/issues/591)) and the tracked timing
  reader ([#592](https://github.com/CVX-Hull/enactive/issues/592)).
- **Nothing is adopted.** ADR 009 stays proposed, and the seven-day screen (#441) stays
  parked.

## Limits

- The answers are decisions on direction. No design is adopted and no run is approved
  by them.
- The two notes rest on one lineage of 47.79 game hours for live memory evidence and
  for response times; each states its own limits.
