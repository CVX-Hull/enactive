---
owner: lead
status: historical
kind: study
date: '2026-11-26'
scope: 'Diagnosis of eight past incidents of this repository from their retained run evidence, for issue #977: seven explorer configurations from three model families, each as tools/delegate.py starts it, given the same evidence and a one-sentence description with the cause withheld, judged by the lead; and the frame-reading start repeated on Gemini 4 Neon; subscription quota only, no game launch, no game input'
---

# Run-evidence diagnosis study

## At a glance

Seven explorer configurations were each given the retained evidence of eight past
incidents and asked for the root cause. The lead compared each answer with the cause
the incident's own dated record states.

| Configuration, as started | States the recorded cause | Stops short of it | Wrong | No reply | Wall time, eight starts |
| --- | ---: | ---: | ---: | ---: | ---: |
| Claude Opus 5.5 at High | 8 | 0 | 0 | 0 | 381 s |
| Claude Opus 5.5 at Medium | 8 | 0 | 0 | 0 | 290 s |
| Gemini 4 Carbon at High | 8 | 0 | 0 | 0 | 2,735 s |
| GPT-6.2 Sol at Extra-high | 6 | 2 | 0 | 0 | 240 s |
| GPT-6.2 Astra at High | 6 | 2 | 0 | 0 | 165 s |
| GPT-6.2 Astra at Medium | 6 | 2 | 0 | 0 | 147 s |
| Gemini 4 Neon at High | 6 | 0 | 0 | 2 | 1,099 s |

No configuration stated a wrong cause. The three GPT-6.2 configurations stopped short
on the same two incidents: each named the failing step correctly and went no further,
where the other configurations inferred the reason. On six of the eight
incidents every configuration that replied stated the recorded cause.

The table does not rank the models. Eight incidents is a small sample, each start ran
once, and the lead judged the answers knowing which configuration wrote each, chose
the incidents and wrote their descriptions. A reviewer from another family judged
every answer again and agreed with all 56 verdicts. Each incident has a cause that a
record of this repository states, and the answers are scored against that cause; the
files given do not always prove it, as the two incidents below show.

Not known: how any configuration does on an incident nobody has diagnosed; whether a
second judge would draw the line between "states" and "stops short" in the same place;
and whether a second run gives the same answer. No owner decision is requested.

The scripts, the scouting reply, every brief, reply and result, the lead's verdicts
and the table are retained as
[`run-evidence-diagnosis`](../../data/evidence/run-evidence-diagnosis.sha256). The
figures here are printed by `scripts/tabulate.py` into `results/table.txt`.

## Method

- **Finding the incidents.** One explorer on Codex GPT-6.2 Sol at Extra-high read the
  dated records and the evidence index for incidents whose cause a record states,
  whose cause was found from the run's own evidence, and whose evidence is still in
  the sealed store (`scout/`). It returned eight, and all eight are used.
- **The fixtures.** For each incident the lead copied the evidence files a reader would
  start from out of the sealed store into a directory that holds nothing else from the
  repository except the explorer role file (`scripts/diagnose.py` names the files).
  Game frames were given neutral numbered names.
- **The brief.** Every configuration got the same brief: one sentence saying what went
  wrong, with the cause withheld, the list of evidence files, an instruction not to
  guess, and a three-line answer of at most 150 words giving cause, evidence and
  confidence. Each start ran once through `tools/delegate.py` as an explorer with a
  900-second limit. The five Claude and GPT-6.2 configurations ran at the same time on
  each incident, and the two Gemini configurations later the same evening, after their
  quota returned.
- **Judging.** The lead read each answer against the cause in the incident's record
  and a criterion written for that incident (`results/judgments.json`). "States" means
  the answer gives the record's cause, as fact or as a marked inference. "Stops short"
  means it identifies the failing step correctly and gives no reason for it, whether
  or not it says the reason is missing. "Wrong" means it gives a different cause.
  Codex GPT-6.2 Astra at High then read every answer against the same records and
  criteria and agreed with all 56 verdicts; its reply is not in the sealed evidence,
  and its ledger row records the attempt.
- **Confinement.** The brief forbids reading outside the fixture. The Codex start
  enforces read-only access but not the directory, the Claude Code start enforces
  neither, and what the Antigravity start enforces is unverified. The evidence files
  contain absolute paths into the repository, where the records that state each cause
  are. No answer cites a file outside its fixture (`grep` over the replies for the
  records and the evidence store). The Codex starts' output keeps each command they
  ran, and the Claude Code and Antigravity starts' output does not keep their file
  reads, so for those two this is not shown beyond the replies.

## The incidents

| Incident | What the brief said | Evidence given | Record that states the cause |
| --- | --- | --- | --- |
| Launch exit | A validation run exited before its first model request | a console log and a receipt, 1 kB | [live validation run](2026-11-22-live-validation-run-889.md) |
| Curator stop | Two curator submissions were rejected and its runner stopped while play continued | a session database, a gate ledger, facts, provenance and a stop file, 1.0 MB | [live curator run](2026-11-21-live-curator-run-859.md) |
| Request not completed | A session ended without a new save after a model request failed to complete | a host event log and a receipt, 258 kB | [campground memory run](2026-11-19-joanna-campground-memory-803.md) |
| Viewer link | The announced viewer address returned an unknown-route error | three small state files, 9 kB | [delivery development start](2026-11-14-delivery-development-start.md) |
| Early end | A session ended before the player quit and the next resumed from an older save | a host event log and a receipt, 2.4 MB | [held-out lineage](2026-11-09-held-out-lineage-522.md) |
| Character death | The character died shortly before a scheduled check | five game frames in time order, 554 kB | [seven-day run](2026-11-07-seven-day-397.md) |
| Map command | An input completed but the map did not center on the destination | a host event log and two game frames, 706 kB | [player test diagnostic](2026-11-05-player-test-diagnostic.md) |
| Thirteen requests | A session ended incomplete after thirteen model requests | three watch files and a receipt, 9 kB | [player test diagnostic](2026-11-05-player-test-diagnostic.md) |

## Results by incident

Each cell is the lead's verdict and the start's wall time in seconds.

| Incident | Opus High | Opus Medium | Astra High | Astra Medium | Sol Extra-high | Carbon High | Neon High |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Launch exit | states, 18 | states, 18 | short, 16 | short, 15 | short, 16 | states, 197 | states, 52 |
| Curator stop | states, 109 | states, 59 | states, 39 | states, 36 | states, 64 | states, 346 | no reply, 21 |
| Request not completed | states, 55 | states, 61 | states, 15 | states, 13 | states, 23 | states, 349 | states, 127 |
| Viewer link | states, 20 | states, 17 | states, 19 | states, 14 | states, 18 | states, 474 | states, 88 |
| Early end | states, 50 | states, 43 | states, 13 | states, 18 | states, 28 | states, 324 | states, 117 |
| Character death | states, 43 | states, 22 | short, 20 | short, 17 | short, 22 | states, 352 | states, 471 |
| Map command | states, 37 | states, 38 | states, 23 | states, 21 | states, 42 | states, 320 | no reply, 24 |
| Thirteen requests | states, 49 | states, 32 | states, 20 | states, 13 | states, 27 | states, 373 | states, 199 |

- **Launch exit.** The record's cause is that the launcher redirected output into a
  logs directory that did not exist. The console log shows only that the log file could
  not be opened. The GPT-6.2 answers stop at that line. The Claude Opus 5.5 and Gemini
  answers say the directory was missing and mark it as an inference or as likely.
- **Character death.** The record's cause is that the character caught fire starting a
  craft beside a fuelled fire. The GPT-6.2 answers say the character burned while
  crafting and that the frames do not show what ignited it. The others tie the burning
  to the fire the craft used; Gemini 4 Neon adds that the exact ignition is not shown.
- **The two empty replies.** Gemini 4 Neon asked to run a command, the read-only print
  mode denied it, and the run ended with no reply. The
  [reviewer recall replay](2026-11-25-reviewer-recall-replay.md#the-gemini-starts)
  records the same failure on review briefs.

Token counts as each coding agent reported them, for eight starts, compare within a
coding agent only: Claude Opus 5.5 at High 2.2 million cached input, 264,000 cache
write and 22,000 output, and at Medium 1.7 million, 243,000 and 16,000; GPT-6.2 Astra
at High 841,000 input and 3,000 output, and at Medium 724,000 and 2,600; GPT-6.2 Sol
at Extra-high 984,000 and 8,600; Gemini 4 Carbon 835,000 input, 2.1 million cached and
235,000 output; Gemini 4 Neon 407,000, 987,000 and 123,000.

## Frame reading on Gemini 4 Neon

The [delegate start probes](2026-11-25-delegate-start-probes.md#frame-reading) could
not test Gemini 4 Neon, whose start was refused on quota. The same brief and frames
were started once more on Gemini 4 Neon at High after the quota returned
(`frame-reading-neon/`). It opened both frames with its file-reading tool and answered
8 of 8 questions as the key has them, in 42 seconds. The lead compared the answers with
the key.

## What this supports

Every statement is about these eight incidents, each configuration as started here and
run once.

- Every configuration that replied named the failing step of every incident, and none
  stated a wrong cause.
- Where the evidence shows a failure and not its reason, the GPT-6.2 configurations
  stopped at what was shown, and on four of those six answers said the rest was
  missing. The Claude Opus 5.5 and Gemini configurations inferred the reason and
  matched the recorded cause both times. Two incidents do not show whether that
  inference is reliable.
- Effort made no difference to the verdicts for the two models run at two efforts.
- GPT-6.2 Astra at Medium took the least time, 13 to 36 seconds a start, and Gemini 4
  Carbon the most, 197 to 474 seconds.
- Gemini 4 Neon at High returned no reply on two of eight explorer starts, and reads
  text and a highlighted button from a retained frame correctly.
