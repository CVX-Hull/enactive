---
owner: lead
status: historical
kind: measurement
date: '2026-11-13'
scope: 'The tracked host trace reader (tools/host_analysis.py) run on the sealed player-host traces of the seven-day lineage (#397), the long-horizon arm (#382), the six sampled development-loop runs (#372) and the held-out lineage (#522): response time by prompt size, share of responses within 2 s and 5 s, interval between tool results, mean cost per request; aggregates only, $0, no model call, no game launch (#592)'
---

# Host response time by prompt size on the sealed lineages

## At a glance

- **Question.** Can the tracked reader, `tools/host_analysis.py`, produce the response-time
  figures by prompt size that the [cadence plan](../design/cadence-plan.md#what-the-sealed-traces-show)
  took from a one-off script, and what do the other sealed lineages show?
- **Answer.** On the seven-day lineage (#397) the reader reproduces the cadence plan's
  counts and medians exactly. Its nearest-rank 95th percentiles equal the
  [memory note](../design/long-horizon-memory.md#memory-and-response-time)'s in four of the
  five prompt-size bands; in the smallest band the reader gives 5.2 s and the note 5.3 s. They
  equal the cadence plan's interpolated values in four bands; in the largest the reader gives
  14.0 s and the plan 13.9 s
  ([the comparison](#reproducing-the-cadence-plan-on-the-seven-day-lineage)). The same
  reader on #382, the #372 sample and #522 shows the same pattern in each: the median response grows with
  prompt size, and no response to a prompt of 20,000 tokens or more finished within 2 s.
- **Not known.** Why. Prompt size is confounded with how far into an admission the actor is,
  with the number of images and with the size of the request body, as the cadence plan says.
  The host records no time for server inference or provider load, so it cannot say why the
  same band was slower in #522 than in #397. All four sets ran on one route.
- **Owner decisions needed.** None. This costs nothing and decides nothing.

Every figure below comes from the command printed above its table. Each command is run from
the root of a checkout that contains this change, with `EVIDENCE` set to the directory
that holds the sealed studies (in the main checkout, `.runtime/evidence`; the
[evidence store](../operations/evidence-cleanup.md) page describes it). The sealed copies were
read in place. The fast check of the day verified each study's file set, byte total and read-only
state against its tracked manifest; it did not re-hash the files' contents.

## What the reader reports now

`tools/host_analysis.py` is the one reader of host traces; `tools/evaluate.py host-summary`
prints it. It already reported time to headers, to the first tool argument and to completion.
It now also reports, for each trace, for each run (the directory that holds `actors/NNN/host.jsonl`)
and for the whole selection, under the key `response_by_prompt`:

- the response time (`request-start` to `response-complete`, by `monotonic_ms`) of completed
  responses: count, median and 95th percentile, nearest rank as everywhere in the tool;
- the same for five bands of prompt tokens (input plus cache read plus cache write): under 20,000;
  20,000 to 60,000; 60,000 to 100,000; 100,000 to 150,000; over 150,000. A band includes its
  lower bound, so exactly 20,000 tokens is in the second band and exactly 150,000 in the last;
- the share of responses within 2 s and within 5 s (at most 2,000 ms and 5,000 ms);
- the mean cost per request in dollars, from the provider-reported `usage.cost.total`, over the
  responses that report one;
- the interval from one request's first tool result to the next request's first tool result.
  A request with no tool result neither ends nor starts an interval. In #397 no request has
  more than one tool result, so this equals the one-off script's measure from the latest
  earlier tool result to a request's first.

A censored request (one that ended in an error or an abort) is not a sample. A response whose
prompt size is not recorded is counted in the whole figure but in no band, and a response with
no reported cost is counted in its band but not in its mean cost. In these four sets every
completed response has both, so the first rule changed nothing here.
`--format markdown` prints the selection's band table and a table by run; `--format json`
prints every field, including each trace's own bands.

## Reproducing the cadence plan on the seven-day lineage

```
.venv/bin/python -m tools.evaluate host-summary --format markdown "$EVIDENCE"/397-seven-day/computer-sessions/sd1a*
```

That is the 14 `host.jsonl` traces of `sd1a1` to `sd1a7` (two actors each), 1,978 request
attempts, none censored, all with usage. The cadence plan's values are in the first number of
each pair; the second is the reader's. The exact 95th percentiles in milliseconds are the
`p95` fields of the same command without `--format markdown`
(`selection.response_by_prompt.bands[].response_ms.p95`).

| Prompt tokens | Responses | Median | 95th percentile, cadence plan (interpolated) | 95th percentile, memory note | 95th percentile, reader (nearest rank) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Under 20,000 | 160 and 160 | 2.7 s and 2.7 s | 5.2 s | 5.3 s | 5.2 s (5,154 ms) |
| 20,000 to 60,000 | 386 and 386 | 5.1 s and 5.1 s | 8.0 s | 8.0 s | 8.0 s (7,977 ms) |
| 60,000 to 100,000 | 514 and 514 | 6.9 s and 6.9 s | 11.4 s | 11.4 s | 11.4 s (11,411 ms) |
| 100,000 to 150,000 | 421 and 421 | 7.7 s and 7.7 s | 11.7 s | 11.7 s | 11.7 s (11,672 ms) |
| Over 150,000 | 497 and 497 | 9.0 s and 9.0 s | 13.9 s | 14.0 s | 14.0 s (13,993 ms) |
| All responses | 1,978 and 1,978 | 7.0 s and 7.0 s | 12.2 s | not given | 12.2 s (12,184 ms) |

The reader also gives the cadence plan's other figures for the whole lineage: 1.6% of responses
within 2 s and 20.5% within 5 s; a maximum of 21.8 s; 1,955 intervals from one request's first
tool result to the next, with median 7.6 s, 95th percentile 12.9 s, 0.1% within 2 s and 13.9% within
5 s; and, by band, within 5 s of 93.8%, 48.2%, 10.3%, 3.3% and 0.4%, and a mean cost per
request of \$0.0030, \$0.0062, \$0.0150, \$0.0234 and \$0.0362. Per actor trace the median is 4.7 to 8.2 s
and the 95th percentile 8.1 to 13.7 s, the ranges the cadence plan quotes.

**The differences.** In the largest band the cadence plan's 13.9 s is interpolated; the nearest-rank
value is 14.0 s, which is the memory note's. In the smallest band the memory note prints 5.3 s, and
the cadence plan calls that the nearest-rank value. The nearest-rank 95th percentile of 160 responses
is the 152nd in order, 5,154 ms. The 153rd is 5,272 ms, which rounds to 5.3 s. The reader uses the
evaluator's `nearest_rank` and reports 5.2 s, which is also the cadence plan's interpolated value. The
memory note's 5.3 s is therefore not the nearest-rank value of these traces. Both notes are decided,
dated design notes that this change does not edit; their owner decides whether to correct the 5.3 s.
No figure was changed to match.

## The other sealed lineages

All 54 traces below were written by the same route as #397: `openai/gpt-6.1-terra` through
OpenRouter at medium effort with at most 39 images and a 262,144-token window, as each trace's
`host-start` event records. The traces are `player-host/3` and are read through the closed archive
index, as the reader does for any older trace.

**Long-horizon arm (#382).** The three lineages `lh1`, `lh2` and `lh3` are pooled: seven admissions,
13 traces (`lh1a2` has one actor trace), 1,610 attempts, none censored. These are the sessions the
[probe protocol](../design/probe-protocol.md) calls held out; this record reads timing and token
counts only, no frame, memory, report or prompt.

```
.venv/bin/python -m tools.evaluate host-summary --format markdown "$EVIDENCE"/372-382-dev-loop/computer-sessions/lh[123]a*
```

| Prompt tokens | Responses | Median s | 95th percentile s | Within 2 s | Within 5 s | Mean cost per request |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All responses | 1,610 | 6.2 | 10.0 | 2.0% | 26.2% | \$0.0189 |
| Under 20,000 | 139 | 2.8 | 5.9 | 23.7% | 88.5% | \$0.0032 |
| 20,000 to 60,000 | 336 | 5.1 | 8.5 | 0.0% | 46.4% | \$0.0060 |
| 60,000 to 100,000 | 474 | 6.2 | 9.8 | 0.0% | 20.9% | \$0.0161 |
| 100,000 to 150,000 | 319 | 6.9 | 11.0 | 0.0% | 9.7% | \$0.0242 |
| Over 150,000 | 342 | 7.3 | 10.9 | 0.0% | 3.8% | \$0.0369 |

The intervals from one request's first tool result to the next: 1,588, median 6.9 s, 95th percentile
11.0 s, 0.2% within 2 s, 16.1% within 5 s.

**The #372 sample.** The six development-loop runs the [probe protocol](../design/probe-protocol.md#data)
draws with `random.Random(449)` and the
[curator hosts page](../operations/curator-hosts.md) lists for lineage 372: `aidB3`, `ceil09`,
`ceil07`, `ceil05`, `aidB9`, `aidA5`. The draw was not repeated. Twelve traces, 1,398 attempts, none censored.

```
.venv/bin/python -m tools.evaluate host-summary --format markdown "$EVIDENCE"/372-382-dev-loop/computer-sessions/{aidB3,ceil09,ceil07,ceil05,aidB9,aidA5}
```

| Prompt tokens | Responses | Median s | 95th percentile s | Within 2 s | Within 5 s | Mean cost per request |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All responses | 1,398 | 6.9 | 12.3 | 1.4% | 24.2% | \$0.0161 |
| Under 20,000 | 134 | 2.8 | 5.6 | 14.2% | 89.6% | \$0.0032 |
| 20,000 to 60,000 | 345 | 4.8 | 8.6 | 0.0% | 54.8% | \$0.0059 |
| 60,000 to 100,000 | 464 | 7.1 | 10.4 | 0.0% | 5.6% | \$0.0159 |
| 100,000 to 150,000 | 283 | 8.7 | 13.3 | 0.0% | 0.7% | \$0.0250 |
| Over 150,000 | 172 | 9.8 | 15.9 | 0.0% | 0.6% | \$0.0327 |

The intervals from one request's first tool result to the next: 1,374, median 7.5 s, 95th percentile
13.1 s, 0.1% within 2 s, 16.6% within 5 s.

**The held-out lineage (#522).** All eight sessions in `522-held-out`: `lh4a1`, the admission lost to
infrastructure (one actor trace with one completed response and three censored requests), and the
seven played admissions `lh4b1` to `lh4b7`. Fifteen traces, 1,817 attempts, of which four are censored
(three in `lh4a1`, one in `lh4b3`) and are not samples. `lh4` is held out until scoring; this record
holds aggregates only and reads no frame, memory record, report or prompt.

```
.venv/bin/python -m tools.evaluate host-summary --format markdown "$EVIDENCE"/522-held-out/computer-sessions/lh4*
```

| Prompt tokens | Responses | Median s | 95th percentile s | Within 2 s | Within 5 s | Mean cost per request |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All responses | 1,813 | 8.3 | 13.6 | 1.3% | 12.9% | \$0.0157 |
| Under 20,000 | 155 | 3.5 | 6.3 | 14.8% | 82.6% | \$0.0029 |
| 20,000 to 60,000 | 379 | 6.1 | 10.6 | 0.0% | 24.3% | \$0.0056 |
| 60,000 to 100,000 | 555 | 8.7 | 13.2 | 0.0% | 1.4% | \$0.0154 |
| 100,000 to 150,000 | 498 | 9.6 | 14.3 | 0.0% | 1.0% | \$0.0215 |
| Over 150,000 | 226 | 9.9 | 14.8 | 0.0% | 0.0% | \$0.0294 |

The intervals from one request's first tool result to the next: 1,791, median 9.0 s, 95th percentile
14.5 s, 0.0% within 2 s, 8.4% within 5 s.

## What the four sets show together

Median response in seconds by prompt size, read from the tables above and from the first command.

| Prompt tokens | Seven-day lineage (#397) | Long-horizon arm (#382) | #372 sample | Held-out lineage (#522) |
| --- | ---: | ---: | ---: | ---: |
| Under 20,000 | 2.7 | 2.8 | 2.8 | 3.5 |
| 20,000 to 60,000 | 5.1 | 5.1 | 4.8 | 6.1 |
| 60,000 to 100,000 | 6.9 | 6.2 | 7.1 | 8.7 |
| 100,000 to 150,000 | 7.7 | 6.9 | 8.7 | 9.6 |
| Over 150,000 | 9.0 | 7.3 | 9.8 | 9.9 |

- **The median rises with prompt size in every set.** The median over 150,000 tokens is between
  2.6 and 3.4 times the median under 20,000.
- **No response to a prompt of 20,000 tokens or more finished within 2 s** in any of the 6,799
  completed responses of the four sets. Within the smallest band, 14% to 24% did.
- **A response within 5 s is the rule only under 20,000 tokens.** The share within 5 s falls from
  83% to 94% in the smallest band to at most 4% in the largest.
- **The three middle bands were slower in #522 than in each of the other three sets**, by 0.9 to
  2.7 s at the median. The traces record the route and its settings but not provider load or time of
  day, so this record does not say why.

## What this does not show

- It does not say that prompt size causes the delay. The cadence plan's account of the
  confounds applies unchanged to all four sets, and #382, the #372 sample and #522 add no way to
  separate them.
- All four sets are one model on one route, and the figures are one reading of retained
  traces. They say nothing about another model, route or service tier.
- The host clock times the interval from sending a request to the completed response. It does not
  time server inference, queueing or the display.
- The bands of the #372 sample hold 134 to 464 responses each, and the largest band 172, so its
  95th percentiles rest on fewer samples than the seven-day lineage's.

Neither the evidence nor any record was changed. The cadence plan and the memory note keep the
figures they print; the one difference is stated above.
