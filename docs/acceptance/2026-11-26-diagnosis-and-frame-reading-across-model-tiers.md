---
owner: lead
status: historical
kind: study
date: '2026-11-26'
scope: 'The run-evidence diagnosis fixture and the frame-reading probe repeated on fourteen configurations the first studies left out, for issues #988 and #989: Claude Fable 5.2, Sonnet 5.5 and Haiku 5.5 on Claude Code; GPT-6.1 Terra and GPT-6 Luna on Codex; Gemini 4 Hydrogen and Argon, Gemini 3.8 Flash, GPT-OSS 120B, Claude Opus 5.5 and Claude Sonnet 5.5 on Antigravity; each as tools/delegate.py starts it, judged by the lead and again by a second family; subscription quota only, no game launch, no game input'
---

# Diagnosis and frame reading across model tiers

## At a glance

The [run-evidence diagnosis study](2026-11-26-run-evidence-diagnosis.md) and the
[frame-reading probe](2026-11-25-delegate-start-probes.md#frame-reading) covered the
largest models of each family. This study gives the same eight incidents, the same
briefs and the same two frames to fourteen configurations those studies left out.

| Configuration, as started | States the recorded cause | Stops short | Wrong | No answer or no reply | Wall time, eight starts | Frame answers right |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude Fable 5.2 at High | 8 | 0 | 0 | 0 | 467 s | 8 of 8 |
| Gemini 4 Argon at High | 8 | 0 | 0 | 0 | 615 s | 8 of 8 |
| Claude Sonnet 5.5 at High | 7 | 1 | 0 | 0 | 245 s | 8 of 8 |
| Claude Sonnet 5.5 at Medium | 7 | 1 | 0 | 0 | 154 s | 8 of 8 |
| GPT-6 Luna at High | 6 | 2 | 0 | 0 | 241 s | 8 of 8 |
| Claude Haiku 5.5 at High | 5 | 2 | 1 | 0 | 407 s | 8 of 8 |
| GPT-6.1 Terra at Medium | 5 | 3 | 0 | 0 | 121 s | 8 of 8 |
| GPT-6.1 Terra at High | 4 | 4 | 0 | 0 | 140 s | 8 of 8 |
| Gemini 4 Hydrogen at High | 4 | 2 | 0 | 2 | 341 s | 8 of 8 |
| Gemini 3.8 Flash at High | 3 | 0 | 0 | 5 | 327 s | 8 of 8 |
| GPT-6 Luna at Low | 1 | 7 | 0 | 0 | 100 s | 8 of 8 |
| GPT-OSS 120B at Medium | 0 | 4 | 0 | 4 | 219 s | cannot open an image |
| Claude Sonnet 5.5 through Antigravity at High | 1 | 0 | 0 | 7 | 54 s | 8 of 8 |
| Claude Opus 5.5 through Antigravity at High | 0 | 0 | 0 | 8 | 34 s | no answer |

The verdicts are the lead's. A judge from another family, reading the answers under
codes that hide the model, gave the same verdict on 84 of 88 answers and the same
count on all fourteen frame replies. The four differences are listed
[below](#where-the-judges-differ).

One answer in 88 states a wrong cause: Claude Haiku 5.5 on the curator stop. Every
other answer either states the recorded cause or stops at a step the evidence does
show. Claude Fable 5.2 and Gemini 4 Argon state the recorded cause on all eight
incidents, as Claude Opus 5.5 and Gemini 4 Carbon did in the first study.

Every configuration that can open an image reads the two frames correctly. The
difference between tiers shows in diagnosis, and mostly as stopping short.

On Antigravity, 23 of 40 explorer starts on a model other than Gemini 4 Argon ended
with no reply because the model asked to run a command, which the read-only start
denies. The brief did not tell the model to run no command.

The table does not rank the models. Eight incidents is a small sample and each start
ran once. Not known: whether a second run gives the same answer, and how the
Antigravity starts do when the brief says to run no command, which
[the reviewer-start leaf](https://github.com/CVX-Hull/enactive/issues/986) measures.
No owner decision is requested.

The scripts, every brief, reply and result, both judges' verdicts and the table are
retained as
[`diagnosis-and-frame-reading-across-model-tiers`](../../data/evidence/diagnosis-and-frame-reading-across-model-tiers.sha256).
The figures here are printed by `scripts/tabulate.py` into `results/table.txt`.

## Method

- **What is reused.** The eight incident fixtures, the incident descriptions and the
  explorer brief are the first diagnosis study's; the two frames, the eight questions
  and the key are the frame-reading probe's. `scripts/tiers.py` reads them from the
  copies those studies were sealed from and changes only the configuration named on
  the brief's Role line.
- **The configurations.** Every model the coding agents offer that the first studies
  did not start, at High where the coding agent offers it: GPT-OSS 120B runs at
  Medium, the only effort Antigravity lists for it. Three models also run at the effort
  the routing page names for cheap work: Claude Sonnet 5.5 and GPT-6.1 Terra at Medium
  and GPT-6 Luna at Low. The three Antigravity orchestrator entries are not models and
  are not started.
- **The starts.** Each configuration ran once on each incident as an explorer with a
  900-second limit, and once on the frame brief as a reviewer with a 600-second limit,
  through `tools/delegate.py` on Claude Code 2.1.329, Codex CLI 0.171.0 and
  Antigravity CLI 1.5.17 and 1.5.18. Up to seven starts ran at the same time.
- **Capacity refusals.** Four GPT-OSS 120B starts failed with the server's "no capacity
  available" error. Each was started once more: two answered, one was refused again
  and one ended with no reply. The table counts the second start; the first four are
  kept under `capacity-refused/`.
- **Judging.** The lead read each answer against the cause in the incident's record
  and the first study's criterion for that incident, knowing which configuration wrote
  it (`results/judgments.json`). The levels are the first study's, with one added: "no
  answer" is a hand-back that holds only an opening sentence. Codex GPT-6.2 Astra at
  High then judged all 88 non-empty answers and the fourteen frame replies from a
  packet that shows the recorded cause, the criterion and each answer under a shuffled
  code (`judge/`, `results/codes.json`).
- **Confinement.** As in the first study, the brief forbids reading outside the
  fixture and no start enforces the directory. No answer cites a dated record or the
  evidence store.

## Results by incident

Each cell is the lead's verdict and the start's wall time in seconds. "none" is an
empty reply, a failed start or a hand-back with no answer.

| Incident | Fable High | Sonnet High | Sonnet Medium | Haiku High | Terra High | Terra Medium | Luna High | Luna Low |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Launch exit | states, 23 | states, 15 | states, 11 | short, 15 | short, 14 | short, 12 | states, 16 | short, 9 |
| Curator stop | states, 97 | short, 58 | short, 33 | wrong, 91 | short, 20 | short, 21 | short, 42 | short, 22 |
| Request not completed | states, 44 | states, 23 | states, 16 | states, 29 | states, 15 | states, 10 | states, 20 | short, 8 |
| Viewer link | states, 33 | states, 18 | states, 9 | states, 29 | states, 14 | states, 11 | states, 22 | states, 10 |
| Early end | states, 71 | states, 18 | states, 19 | states, 67 | states, 16 | states, 14 | states, 33 | short, 8 |
| Character death | states, 70 | states, 30 | states, 22 | states, 34 | short, 22 | states, 13 | states, 29 | short, 13 |
| Map command | states, 88 | states, 56 | states, 28 | states, 87 | states, 29 | states, 29 | short, 59 | short, 20 |
| Thirteen requests | states, 41 | states, 27 | states, 16 | short, 55 | short, 10 | short, 11 | states, 20 | short, 10 |

| Incident | Hydrogen High | Argon High | Flash High | GPT-OSS Medium | Opus through Antigravity | Sonnet through Antigravity |
| --- | --- | --- | --- | --- | --- | --- |
| Launch exit | short, 27 | states, 30 | states, 29 | short, 34 | none, 4 | none, 4 |
| Curator stop | short, 70 | states, 159 | none, 26 | short, 30 | none, 4 | none, 4 |
| Request not completed | states, 65 | states, 79 | none, 18 | none, 21 | none, 5 | none, 4 |
| Viewer link | states, 34 | states, 51 | states, 97 | none, 20 | none, 4 | none, 3 |
| Early end | none, 10 | states, 93 | none, 34 | none, 39 | none, 4 | none, 4 |
| Character death | states, 62 | states, 57 | states, 64 | none, 15 | none, 4 | states, 28 |
| Map command | none, 12 | states, 70 | none, 20 | short, 29 | none, 5 | none, 3 |
| Thirteen requests | states, 61 | states, 76 | none, 39 | short, 31 | none, 4 | none, 4 |

- **Curator stop is the incident that separates the tiers.** Its cause is in a session
  database: two operations returned the same frame, and a later publication overwrote
  the frame's step. Only Claude Fable 5.2 and Gemini 4 Argon found it, as every
  configuration that replied did in the first study. Eight others reported the gate's
  rejection message and said the reason was not shown.
- **The wrong cause.** Claude Haiku 5.5 proposed, as likely, that the rejected sessions
  cited frames the published history never admitted. It marked the link as inferred.
  The same reply says it wrote three scratch files outside the fixture, against the
  brief, and removed them.
- **Thirteen requests.** The watch file names the watch deadline. Claude Haiku 5.5,
  both GPT-6.1 Terra efforts, GPT-6 Luna at Low and GPT-OSS 120B reported the
  cancellation and did not connect it to the deadline.
- **Map command.** GPT-6 Luna at High read the input as Shift+C and then misread the
  frame's legend as giving that key to "Center on destination", so it called the cause
  not shown. GPT-OSS 120B said the event log holds no map-centering input, which it
  does.
- **Effort.** Claude Sonnet 5.5 gives the same eight verdicts at High and Medium.
  GPT-6.1 Terra differs on one. GPT-6 Luna states the cause on six at High and on one
  at Low, where its answers take 8 to 22 seconds.
- **No reply.** All 23 empty replies on Antigravity follow a denied command: 7 of 8
  starts on Claude Opus 5.5, 6 on Claude Sonnet 5.5, 5 on Gemini 3.8 Flash, 3 on
  GPT-OSS 120B and 2 on Gemini 4 Hydrogen. Gemini 4 Argon ran no command and replied
  on all eight. The two Claude models through Antigravity each handed back one opening
  sentence as if it were an answer, and the call reports those as handed back.

Token counts as each coding agent reported them, for eight starts, compare within a
coding agent only. Claude Code: Fable 5.2 2.0 million cached input, 322,000 cache
write and 36,000 output; Sonnet 5.5 at High 1.8 million, 264,000 and 24,000, and at
Medium 1.4 million, 232,000 and 14,000; Haiku 5.5 2.5 million, 334,000 and 69,000.
Codex: Terra at High 839,000 input and 3,500 output, and at Medium 709,000 and 2,900;
Luna at High 990,000 and 9,600, and at Low 845,000 and 2,700. Antigravity: Argon
667,000 input, 864,000 cached and 49,000 output; Hydrogen 391,000, 798,000 and 65,000;
Flash 288,000, 436,000 and 36,000.

## Where the judges differ

| Answer | Lead | Second judge | The difference |
| --- | --- | --- | --- |
| GPT-6.1 Terra at High, request not completed | states | short | The answer names the 502 and the timeout before the retry, and not the retry delay. |
| GPT-6.1 Terra at Medium, request not completed | states | short | "Timed out before a retry completed" leaves open whether a second attempt began. |
| GPT-6 Luna at Low, early end | short | states | The answer names the context limit and the SIGTERM and says the cause is not shown. |
| GPT-6 Luna at High, map command | short | wrong | The answer misreads the legend and concludes the cause is not shown. |

Counting only answers both judges call "states", GPT-6.1 Terra has 3 at High and 4 at
Medium; the other rows of the first table do not change.

## Frame reading

Each configuration got the two frames and eight questions once.

| Configuration | Opened both frames with | Answers that match the key | Wall time |
| --- | --- | ---: | ---: |
| Claude Fable 5.2 at High | the file-reading tool | 8 | 34 s |
| Claude Sonnet 5.5 at High | the file-reading tool | 8 | 13 s |
| Claude Sonnet 5.5 at Medium | the file-reading tool | 8 | 11 s |
| Claude Haiku 5.5 at High | the file-reading tool | 8 | 16 s |
| GPT-6.1 Terra at High | the image viewer | 8 | 11 s |
| GPT-6.1 Terra at Medium | the image viewer | 8 | 14 s |
| GPT-6 Luna at High | the image viewer | 8 | 21 s |
| GPT-6 Luna at Low | the image viewer | 8 | 11 s |
| Gemini 4 Hydrogen at High | the file-reading tool | 8 | 19 s |
| Gemini 4 Argon at High | the file-reading tool | 8 | 37 s |
| Gemini 3.8 Flash at High | the file-reading tool | 8 | 52 s |
| Claude Sonnet 5.5 through Antigravity at High | the file-reading tool | 8 | 9 s |
| GPT-OSS 120B at Medium | could not open either | 0 | 24 s |
| Claude Opus 5.5 through Antigravity at High | no answer | 0 | 10 s |

GPT-OSS 120B said it has no tool that renders an image and answered nothing, as the
brief asks. Claude Opus 5.5 through Antigravity handed back two sentences saying it
would read the role file, and no answers.

Four Claude Code frame replies and one diagnosis reply mention plan mode or carry the
session owner's explanatory note blocks, as the
[reviewer recall replay](2026-11-25-reviewer-recall-replay.md) found for this start.

## What this supports

Every statement is about these eight incidents and two frames, each configuration as
started here and run once.

- Reading text and a highlighted button from a frame does not need a large model:
  every configuration that can open an image answers all eight questions correctly,
  the fastest in 9 to 16 seconds. GPT-OSS 120B cannot open an image.
- For a cause that takes cross-file work inside a database, only the largest model of
  a family finds it here: Claude Fable 5.2 and Gemini 4 Argon, with Claude Opus 5.5
  and Gemini 4 Carbon from the first study.
- A smaller model usually fails by stopping short, not by stating a wrong cause: one
  wrong cause in 88 answers, from Claude Haiku 5.5.
- Claude Sonnet 5.5 at Medium states seven of eight causes in 9 to 33 seconds a start,
  the same verdicts as at High.
- GPT-6 Luna at Low names a failing step and almost never the cause.
- On Antigravity, only Gemini 4 Argon replied to every explorer brief that does not
  say to run no command. Claude Opus 5.5 and Claude Sonnet 5.5 through Antigravity
  returned an answer on 0 and 1 of 8.
