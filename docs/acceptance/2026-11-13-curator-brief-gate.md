---
owner: lead
status: historical
kind: study
date: '2026-11-13'
scope: 'The brief gate of the memory screen (#460, protocol of 13 November 2026): the curator, with a brief for places and goods and the fact format curator-fact/2, run over the seven-day lineage''s admissions sd1a1 to sd1a6 on the actor''s model, and its store checked against frozen patterns for the four lost facts. Curator sessions only; no game launch'
---

# Curator brief gate on the seven-day lineage (#460)

## At a glance

- **Result: pass, 4 of 4.** The re-briefed curator stored every lost fact as a
  `place_with_goods` fact with its place: the roof tank, the twenty ration boxes in the
  cupboard, the fishing rod on the shelter floor and the battery in a locker. A
  clean-context reviewer confirmed each against its cited frames. The recorded store
  had held one of the four.
- **Cost.** \$15.86 of the \$45 stop, over six sessions and 258 requests. No session
  reached its cap, aborted or was rejected; nothing was re-run.
- **The store is large.** After six admissions `facts.jsonl` holds 195 records in
  102,594 bytes: 172 current, 124 of them places with goods. The subject, place, time and
  text of the current facts come to 33,839 bytes, about 11,100 tokens at 0.327 tokens a
  byte (a rate fitted on tool-result text). The recorded store the protocol's
  simulation sized its briefing from was 36,947 bytes, so the store is 2.8 times larger.
- **Not known.** Whether a player given these facts uses them; that is what the
  comparison would test.
- **Owner decision.** None from this gate; it opens the session price pilot.
- **Spend.** \$15.86 of the \$65 envelope.
- **Pass rule.** At least three of the four lost facts are stored as `place_with_goods`
  facts whose `subject` and `place` match the frozen patterns, each confirmed by a
  clean-context reviewer who answers the question frozen below. Otherwise the gate
  fails and the work stops.
- **Stop.** \$45 for the whole gate, taken from the curator proxy's ledger.

## Frozen inputs

The code and the brief are `main` at `9d30790`. The patterns and this page are frozen
on the branch `memory-screen-gates`, in the commit that last changed the patterns file
before the first session.

| Input | Value | sha256 |
| --- | --- | --- |
| Protocol | `docs/design/memory-screen-protocol.md` | `9aae71f86f2e4d5ad10b64cca3e018206a57a34472ebc7a0ea7432f26568de40` |
| Curator brief | `tools/curator_host/prompt.md` | `c5ca0ce7cc1c191360669b908e67e0d0c80471bf906ec77acbed6ef894360a6b` |
| Check patterns | `docs/acceptance/assets/2026-11-13-curator-brief-gate-patterns.json` | `c04751ad3df45f22fb97eeb6c37346f8938d0af28c7f268dd0b042564589a458` |
| Arm | `terra` in `data/curator/shadow-arms.json`: `openai/gpt-6.1-terra`, provider pinned, effort medium | `4c67015c6265dff372dca2307e98922823d2b18045765503618af5b7525c27d0` |
| Prices | `data/curator/openrouter-prices-2026-11-08.json` | `36edf95cee93d8ebe6b74efbc498386f3f5ba3bb8c8f7e684e1cca1d45bbf197` |

Each run's `summary.json` records `host.prompt_sha256`; it must equal the brief's hash
above.

### The check

The patterns are matched case-insensitively against a fact's `subject` and `place`,
never against its `statement`. Only current facts of kind `place_with_goods` count, and
a fact that matches two labels counts for neither.

| Lost fact | `subject` | `place` | The reviewer's question |
| --- | --- | --- | --- |
| A tank of clean water on the roof | `tank\|clean water` | `roof` | Does the fact say there is a water tank on the shelter's roof? |
| Ration boxes in a cupboard | `ration\|cardboard box` | `cupboard\|cabinet` | Does the fact say the boxes of rations are in the cupboard? The three rations in a locker do not count |
| A fishing rod on the floor of the shelter | `fishing rod` | `shelter\|floor\|ground` | Does the fact say a fishing rod lies inside the shelter? A rod at the lake, or carried, does not count |
| Batteries in a locker | `batter` | `locker` | Does the fact say a battery is in a locker of the shelter? |

A label passes when at least one matching fact gets a yes from a clean-context reviewer
who is shown the fact and its cited frames and not the result wanted.

The first frozen version of the patterns was changed before any session ran, after the
pre-spend review showed honest facts it would miss (a subject such as "clean water" or
"small cardboard boxes") and one pattern that only added false matches (`\brod\b`).

### Sessions and money

- **Sessions.** One per admission, `sd1a1` to `sd1a6`, in order, on one fresh knowledge
  repository. 120 requests, 1,800 s wall clock, 16 context images in blocks of 8, and
  32,768 output tokens, twice the runner's default, because a submission is written in
  one call and this brief asks for more facts.
- **Session cap.** \$12. At the current price bounds one worst-case request reserves
  about \$1.6 to \$1.8, so the cap holds about six. The host tells the curator to start
  writing at \$5.10, refuses reading at \$8.16, and the proxy refuses a request from
  about \$10.3 spent. The dearest recorded session cost \$7.08 under no session cap.
- **A session that reaches its cap** is re-run once at \$24. A second cap stops the gate
  as failed.
- **A session that ends with no accepted submission for another reason** (the request
  limit, the wall clock, a provider error, an output-limit stop, or a rejected
  submission) is re-run once with the same inputs. A second such end stops the gate as
  failed. Every re-run is reported.
- **Run cap.** `--cap-usd` holds for one invocation, so each invocation after the first
  is given \$45 less what has been charged so far. The authority for that figure is the
  sum of `charged` over every `proxy-ledger.jsonl` under the gate's output directories,
  plus any `pending_reserved_usd` in a `proxy-close.json`.
- **Order.** `sd1a1` runs alone and is read end to end before the rest. Then `sd1a2` to
  `sd1a6` run in one invocation on the same repository.
- **The check runs once**, on the version published after `sd1a6`, before anything else
  touches the repository.

Commands, from the main checkout. The patterns file is read from this branch's
worktree:

```bash
.venv/bin/python -m tools.curator_host.shadow --arm terra --lineage 397 --sessions sd1a1 \
  --cap-usd 45 --session-cap-usd 12 --max-output-tokens 32768 --stop-on-reject --stop-on-abort \
  --out .runtime/curator-shadow/brief-gate-first
.venv/bin/python -m tools.curator_host.shadow --arm terra --lineage 397 \
  --sessions sd1a2 sd1a3 sd1a4 sd1a5 sd1a6 --cap-usd REMAINING --session-cap-usd 12 \
  --max-output-tokens 32768 --stop-on-reject --stop-on-abort \
  --knowledge-root .runtime/knowledge/shadow-454/brief-gate-first/terra/397 \
  --out .runtime/curator-shadow/brief-gate-rest
.venv/bin/python -m tools.memory_screen_checks brief-gate \
  .runtime/knowledge/shadow-454/brief-gate-first/terra/397/cdda \
  --patterns .runtime/worktrees/memory-gates/docs/acceptance/assets/2026-11-13-curator-brief-gate-patterns.json
```

A re-run is the second command with the one session named, a new `--out`, the same
`--knowledge-root`, and `--double-session-cap` when the cause was the cap.

## Results

### Sessions

Read from each session's `summary.json` and its proxy ledger under
`.runtime/curator-shadow/brief-gate-first/` and `brief-gate-rest/`. Every proxy closed
settled, with no pending reservation. Both runs recorded the brief's hash `c5ca0ce7…`.

| Admission | Requests | Charged | Wall clock | Largest reservation | Frames viewed | Facts after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `sd1a1` | 55 | \$3.82 | 661 s | \$2.19 | 47 | 64 |
| `sd1a2` | 38 | \$1.90 | 448 s | \$1.93 | 29 | 106 |
| `sd1a3` | 39 | \$2.28 | 385 s | \$1.97 | 29 | 134 |
| `sd1a4` | 25 | \$1.16 | 248 s | \$1.73 | 20 | 153 |
| `sd1a5` | 44 | \$2.51 | 367 s | \$1.85 | 39 | 173 |
| `sd1a6` | 57 | \$4.19 | 497 s | \$2.22 | 55 | 195 |
| **All** | **258** | **\$15.86** | **2,606 s** | | | |

The recorded shadow run, with the earlier brief, spent \$22.32 on the same six
admissions and published 71 facts by its sixth version.

The largest reservations, \$1.73 to \$2.22, were above the frozen estimate of \$1.6 to
\$1.8 in five of six sessions. The \$12 cap still held five of the largest, and the
proxy's refusal point, about \$9.78, still came after the host's reading stop at \$8.16.

### The check

`brief-gate` on version `v6`, patterns `c04751ad…`:

| Lost fact | Matching fact | `subject` / `place` | Reviewer |
| --- | --- | --- | --- |
| Roof tank | `b19-roof-tank` | standing tank of clean water / Evac shelter B-19 roof, near the roof ladder | Yes. The frame shows the tank's menu, 18 L of 300 L, on the shelter's roof at day 62, 8:51 |
| Ration boxes | `b19-pantry-boxes`, `b19-pantry-protein` | small cardboard box of rations, and protein ration in pantry boxes / Evac shelter B-19, cupboard along the east side of the main room | Yes, both. The frames show "20 small cardboard boxes > protein ration" in a cupboard. The third match, `shelter-detergent-box`, is boxes of detergent and does not qualify |
| Fishing rod | `shelter-rod` | basic fishing rod / Evac shelter B-19, main room near the northwestern benches | Yes. The rod lies on the floor between the benches, listed 6 tiles away, not carried |
| Battery | `shelter-battery` | light battery / Evac shelter B-19, southern locker along the east side of the main room | Yes. The battery is listed 1 tile east, on the southernmost of three lockers |

The reviewer saw only the six facts and their cited frames, and was not told the result
wanted. Its doubts, none of which changes an answer:

- Some place details are not shown by the cited frames: no ladder is visible by the
  tank, and the rod's and battery's frames do not name the shelter.
- One ration fact calls the boxes "separate from the locker rations", which its own
  frames do not show.
- The detergent fact's cupboard is a different, southern one.

The rod's place pattern, `shelter|floor|ground`, matched on "Evac shelter B-19", which
every fact about the shelter carries, so it did not discriminate; the reviewer's reading
carries that row.

### Reading the first session

- **What was read.** Before the other five ran, the lead read `sd1a1`'s published facts
  in full (64), its gate verdict, its tool use and its proxy record.
- **What it showed.** Every place-with-goods fact had a place and a time, or "not
  shown". The locker's contents and the rod were already stored, and none of the four
  items was named in the brief.
- **What was not read.** The curator's own transcript, request by request.

## Deviations

- **The patterns and caps were revised before spending.** The pre-spend review found
  honest facts the first patterns would miss, a session cap that a session at the
  recorded size would likely have reached, and no rule for a non-cap stop. The page
  was corrected before the first session, as recorded above.
- **The first session was read by its output, not its transcript**, as stated above.
