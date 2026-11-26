---
owner: lead
status: historical
kind: study
date: '2026-11-26'
scope: 'One lead duty measured across model tiers, for issue #994: ten configurations each check nine past delegate hand-backs against the files they describe, three of which state a fact the files contradict; this measures checking a hand-back and not leading; subscription quota only, no game launch, no game input'
---

# Hand-back verification across model tiers

## At a glance

A lead checks every hand-back against the files before using it. This study asks
whether a cheaper model can do that one duty. Ten configurations each got nine past
hand-backs with the files each described, and said which statements of fact the files
support.

| Verifier, as started | False facts caught, of 3 | Hand-backs of plain facts accepted, of 3 | Wall time, nine checks |
| --- | ---: | ---: | ---: |
| Claude Sonnet 5.5 at Medium | 3 | 3 | 204 s |
| GPT-6.2 Astra at Medium | 3 | 3 | 346 s |
| Claude Haiku 5.5 at High | 3 | 3 | 393 s |
| Claude Opus 5.5 at High, reference | 3 | 3 | 435 s |
| Gemini 4 Neon at High | 3 | 3 | 1,577 s |
| GPT-6.2 Sol at Extra-high, reference | 3 | 2 | 473 s |
| Gemini 4 Hydrogen at High | 3 | 2 | 502 s |
| GPT-6.1 Terra at Medium | 3 | 1 | 233 s |
| GPT-6 Luna at High | 2 | 3 | 394 s |
| GPT-6 Luna at Low | 2 | 3 | 155 s |
| Claude Fable 5.2 at High, added | 3 | 3 | 434 s |
| Gemini 4 Argon at High, added | 3 | 3 | 987 s |
| Gemini 3.8 Flash at High, added | 3 | 3 | 1,699 s |
| Gemini 4 Carbon at High, added | 2 of the 2 it finished | 3 | 5,772 s; three checks stopped at 900 s |
| GPT-OSS 120B at Medium, added | 0: two verdicts in nine starts | 2 | 293 s |

Five configurations were added later the same day so that every model the three coding
agents offer is covered; the sentences below that count "ten" are about the first ten.

- **Eight of ten catch every false fact.** A claim that a log lacks an input it
  records and a constant that exists nowhere in the tree are caught by all ten. A wrong
  quotation of a frame's legend is caught by every configuration except GPT-6 Luna.
- **GPT-6 Luna accepts the misread frame** at both efforts.
- **Seven accept every hand-back that states only plain facts,** and five of those
  also catch all three false facts. The other rejections are one misreading of a frame
  by Gemini 4 Hydrogen, one objection to link paths by GPT-6.1 Terra, and two
  objections that a console error is not shown to have caused the exit.
- **The lead's key was too loose on two hand-backs.** Both state a cause that the files
  do not themselves show, and most verifiers reject them for it. They are reported
  apart and not counted as wrongly rejected.

This measures one lead duty, checking, on nine hand-backs. It does not measure
leading: design, brief writing, adjudication and integration are not tested. No owner
decision is requested.

The scripts, the packets, the key, every reply and result and the table are retained
as
[`hand-back-verification-across-model-tiers`](../../data/evidence/hand-back-verification-across-model-tiers.sha256).
The five added configurations' runs and the full table are retained as
[`hand-back-verification-added-models`](../../data/evidence/hand-back-verification-added-models.sha256).
The figures are printed by `scripts/tabulate.py` into `results/table.txt`.

## Method

- **The hand-backs.** Eight are explorer replies from the
  [diagnosis study across tiers](2026-11-26-diagnosis-and-frame-reading-across-model-tiers.md),
  each with the incident's evidence files as the delegate saw them. The ninth is a
  four-line excerpt of an explorer's report about this repository, with a clone of the
  repository. The model that wrote each is removed (`scripts/build.py`).
- **The key.** The lead fixed an answer for each packet before any start (`key.json`):
  whether its statements hold and, where one does not, which. The lead checked the
  cited lines of the five hand-backs it keyed as sound against the files and read the
  two frames one of them cites.
- **The task.** Each configuration is started once on each packet as a reviewer and
  lists every claim of fact as supported, not supported or not checkable, then gives
  one verdict: accept when every claim it could check is supported, reject otherwise.
  The brief says that a statement the hand-back marks as its own inference is not a
  claim of fact, and not to judge whether the conclusion is the best one.
- **The configurations.** Two references, Claude Opus 5.5 at High and GPT-6.2 Sol at
  Extra-high, and eight others at the effort the routing page uses them at: Claude
  Sonnet 5.5 and GPT-6.2 Astra and GPT-6.1 Terra at Medium, Claude Haiku 5.5 at High,
  GPT-6 Luna at High and Low, Gemini 4 Neon and Hydrogen at High. Each ran through
  `tools/delegate.py` with a 900-second limit, on Claude Code 2.1.329, Codex CLI
  0.171.0 and Antigravity CLI 1.5.18. All ninety starts handed back with a verdict.
- **Added configurations.** Claude Fable 5.2, Gemini 4 Carbon, Gemini 4 Argon and
  Gemini 3.8 Flash at High and GPT-OSS 120B at Medium, the models the first run left
  out, three of which leave Antigravity on 30 November 2026. Of their 45 starts, 35
  give a verdict: Gemini 4 Carbon is stopped at the 900-second limit on three, and
  GPT-OSS 120B fails on the server's capacity error on three, returns nothing on three
  and hands back without a verdict on one.
- **Scoring.** A false fact counts as caught when the verdict is reject and a
  not-supported line names the keyed claim; the lead read those lines.

## The packets

| Packet | Hand-back | The lead's key | Group |
| --- | --- | --- | --- |
| 1 | a map command: the input, the two key bindings and what changed between two frames | holds | plain facts |
| 2 | the same incident: says a frame shows "C - Center on destination" | the legend gives lowercase `c` to centering | false fact |
| 3 | a launch exit: the console line and the receipt | holds | plain facts |
| 4 | the same map incident: says the log holds no map-centering action | line 542 records the Shift+C input | false fact |
| 5 | a viewer link: two port numbers, and that the mismatch explains an unknown route | holds, by the key | states a cause |
| 6 | a curator stop: proposes a wrong cause and marks it as inferred | the cause is not the recorded one | inference |
| 7 | a session ended by a watch deadline: the files' reasons, and their order | holds, by the key | states a cause |
| 8 | a request that did not complete: status, retry delay and timeout lines | holds | plain facts |
| 9 | curator stop rules: a constant `LOOK_FAILURES = 3` | no such constant; the file has `SNAPSHOT_FAILURES` | false fact |

**Where the key fell short.** Packets 5 and 7 cite facts that hold and then state a
cause: that a port mismatch explains an unknown-route response, and that a watch
ended a host. No file in packet 5 records the response, and none in packet 7 says
that one event caused the next. The lead keyed both as sound because their conclusions
match the recorded cause. Eight of ten verifiers reject packet 5 and five reject
packet 7, for a causal statement. Four of those who check packet 7's order of events
against the timestamps mark the order supported. Packet 6 is the reverse: its false element is a marked inference, which the
brief excludes, and no verifier names it.

## Results

| Verifier | False facts caught | Plain facts accepted | Packets 5 and 7 accepted | Packet 6 | Wall time, range |
| --- | ---: | ---: | ---: | --- | --- |
| Claude Sonnet 5.5 at Medium | 3 | 3 | 1 | reject | 13 to 43 s |
| GPT-6.2 Astra at Medium | 3 | 3 | 0 | accept | 24 to 56 s |
| Claude Haiku 5.5 at High | 3 | 3 | 1 | reject | 19 to 90 s |
| Claude Opus 5.5 at High | 3 | 3 | 1 | accept | 31 to 106 s |
| Gemini 4 Neon at High | 3 | 3 | 1 | accept | 98 to 421 s |
| GPT-6.2 Sol at Extra-high | 3 | 2 | 0 | reject | 31 to 99 s |
| Gemini 4 Hydrogen at High | 3 | 2 | 1 | accept | 30 to 76 s |
| GPT-6.1 Terra at Medium | 3 | 1 | 0 | reject | 18 to 35 s |
| GPT-6 Luna at High | 2 | 3 | 1 | reject | 18 to 87 s |
| GPT-6 Luna at Low | 2 | 3 | 1 | accept | 8 to 27 s |
| Claude Fable 5.2 at High, added | 3 | 3 | 1 | accept | 29 to 105 s |
| Gemini 4 Argon at High, added | 3 | 3 | 2 | accept | 42 to 255 s |
| Gemini 3.8 Flash at High, added | 3 | 3 | 2 | accept | 90 to 308 s |
| Gemini 4 Carbon at High, added | 2 of 2 | 3 | none finished | accept | 323 to 901 s |
| GPT-OSS 120B at Medium, added | 0 | 2 | none | none | 8 to 72 s |

- **The false fact GPT-6 Luna misses** is the frame legend. GPT-6 Luna at High wrote
  that hand-back in the diagnosis study, and accepts it here too. On packet 4 GPT-6
  Luna at Low rejects the right claim for a weaker reason: it cites other keypresses
  in the log and does not find the Shift+C input.
- **Rejections of plain-fact hand-backs.** Gemini 4 Hydrogen rejects packet 1, saying
  a city label is still in the second frame; the lead's reading of the frame is that
  it is gone. GPT-6.1 Terra rejects packet 1 because the hand-back's links point to
  the directory root and the files are under `evidence/`. GPT-6.2 Sol and GPT-6.1
  Terra reject packet 3 because it says the missing path caused the launcher to fail:
  the console reports the error and the receipt the exit, and neither says one caused
  the other.
- **How strict a verifier is.** The three GPT-6.2 and GPT-6.1 verifiers accept neither
  causal hand-back; every other verifier accepts one of the two.
- **Tokens,** as each coding agent reported them for nine checks, compare within a
  coding agent only: Claude Sonnet 5.5 1.7 million cached input and 21,000 output;
  Claude Haiku 5.5 3.1 million and 64,000; Claude Opus 5.5 2.6 million and 29,000;
  GPT-6.1 Terra 1.2 million input and 6,400 output; GPT-6.2 Astra 1.2 million and
  5,000; GPT-6.2 Sol 1.5 million and 16,000; GPT-6 Luna 1.3 million and 17,000 at High
  and 1.1 million and 4,200 at Low; Gemini 4 Neon 746,000 input, 1.6 million cached and
  164,000 output; Gemini 4 Hydrogen 747,000, 1.6 million and 99,000.

## What this supports

Every statement is about these nine hand-backs, each verifier as started here and run
once.

- A middle or small model catches a false statement of fact in a hand-back as reliably
  as the two references: Claude Sonnet 5.5 at Medium, Claude Haiku 5.5 at High, GPT-6.2
  Astra at Medium, GPT-6.1 Terra at Medium and both Gemini 4 models catch all three.
- GPT-6 Luna misses a false statement about a frame at either effort.
- The GPT-6.2 and GPT-6.1 verifiers hold a hand-back to what the files literally show,
  rejecting a stated cause the files do not record; the Claude, Gemini and GPT-6 Luna
  verifiers let more of those through. Which is wanted depends on the check, and the lead's own key let two
  through.
- Of the five added configurations, Claude Fable 5.2, Gemini 4 Argon and Gemini 3.8
  Flash catch all three false facts and accept every plain-fact hand-back; Argon and
  Flash also accept both hand-backs that state an unrecorded cause. Gemini 4 Carbon
  does not finish a third of its checks in 900 seconds, and GPT-OSS 120B gives two
  verdicts in nine starts.
- Among the first ten, checking nine hand-backs takes 155 to 502 seconds for every verifier but Gemini 4
  Neon, which takes 1,577.
- Nothing here shows a cheaper model can lead. It shows that checking a hand-back
  against its files is work a cheaper model does.
