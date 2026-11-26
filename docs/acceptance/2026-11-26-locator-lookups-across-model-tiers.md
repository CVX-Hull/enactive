---
owner: lead
status: historical
kind: study
date: '2026-11-26'
scope: 'Fourteen lookups with answers fixed from the tree at one commit, given to eleven locator configurations on Claude Code, Codex and Antigravity through tools/delegate.py, for issue #990; subscription quota only, no game launch, no game input'
---

# Locator lookups across model tiers

## At a glance

The locator role finds where a thing is: a path, a line, a short quotation. Eleven
configurations each got the same fourteen lookups about this repository at one commit,
with every answer fixed from the tree beforehand.

| Configuration, as started | Exact | Says not found for a thing that exists | States a wrong location | Wall time |
| --- | ---: | ---: | ---: | ---: |
| Claude Haiku 5.5 at Low | 14 | 0 | 0 | 17 s |
| GPT-6.1 Terra at Medium | 14 | 0 | 0 | 18 s |
| Claude Sonnet 5.5 at Medium | 14 | 0 | 0 | 18 s |
| GPT-6.1 Terra at High | 14 | 0 | 0 | 19 s |
| Claude Sonnet 5.5 at High | 14 | 0 | 0 | 21 s |
| GPT-6.2 Sol at Extra-high, the reference | 14 | 0 | 0 | 28 s |
| Claude Haiku 5.5 at High | 14 | 0 | 0 | 32 s |
| GPT-6 Luna at High | 14 | 0 | 0 | 32 s |
| GPT-6 Luna at Low | 13 | 1 | 0 | 22 s |
| Gemini 4 Neon at High | 13 | 1 | 0 | 355 s |
| Gemini 4 Hydrogen at High | 13 | 1 | 0 | 509 s |

- **No configuration states a wrong location.** Every answer that names a path and
  line is right, and all eleven say "not found" for the two things that do not exist.
- **The one miss is the same lookup three times.** A class defined in a test file is
  reported as not found by GPT-6 Luna at Low and by both Gemini 4 configurations.
- **The set barely separates quality and clearly separates time.** Eight of eleven
  answer everything in 17 to 32 seconds. The two Gemini 4 configurations take 355 and
  509 seconds; their starts have no shell to search with.
- **Small models do this work as well as the reference.** Claude Haiku 5.5 at either
  effort and GPT-6 Luna at High match it; GPT-6 Luna at Low misses one lookup. The
  route's choice of the smallest model for locating is supported here, for lookups of
  this kind.

Limits: fourteen lookups, one start each, all in one brief; every lookup has a single
searchable name; nothing here tests a lookup that needs judgment. One answer in the key
was incomplete and a reply showed it ([the key](#the-lookups)). No owner decision is
requested.

The scripts, the key, every brief, reply and result and the table are retained as
[`locator-lookups-across-model-tiers`](../../data/evidence/locator-lookups-across-model-tiers.sha256).
The figures here are printed by `scripts/score.py` into `results/table.txt`.

## Method

- **The tree.** A shallow clone of this repository at `8f7b9158`, holding nothing else.
- **The lookups.** Fourteen, in the four kinds the leaf names: where a name is defined
  (five), where a rule or term is stated (four), a caller, every caller or every
  definition of a function (three), and two whose correct answer is that the thing
  does not exist. The
  lead fixed each answer with `git grep` before any start (`key.json`).
- **The brief.** One brief holds all fourteen lookups and asks for one line each: the
  path and line, the value or words where the lookup asks for them, or "not found". It
  says that a lookup's answer may be that the thing does not exist, and not to guess.
- **The configurations.** Each smaller model at its routing-default effort and at High:
  Claude Haiku 5.5 at Low and High, GPT-6 Luna at Low and High, GPT-6.1 Terra at Medium
  and High, Claude Sonnet 5.5 at Medium and High. Gemini 4 Hydrogen and Gemini 4 Neon
  at High, since Antigravity's smaller models leave on 30 November 2026. GPT-6.2 Sol at
  Extra-high is the reference. Each ran once as a locator through `tools/delegate.py`
  with a 900-second limit, on Claude Code 2.1.329, Codex CLI 0.171.0 and Antigravity
  CLI 1.5.18.
- **The starts.** The Claude Code starts use the `dontAsk` permission mode of the
  [start check](2026-11-26-reviewer-start-check.md), before the file-reading tools were
  allowed outside the working directory; every lookup is inside it. The Antigravity
  starts carry the call's note to run no shell command.
- **Scoring.** `scripts/score.py` reads each reply against the key. An answer is exact
  when it names every keyed path and line and no other, with the keyed value where one
  is asked, or says "not found" for a thing that does not exist. Line numbers must match
  exactly.

## The lookups

| Lookup | Kind | Answer |
| --- | --- | --- |
| Where `capture_headroom` is defined | definition | `tools/campaign_package.py:276` |
| The line outside the tests that calls it | caller | `tools/campaign_package.py:310` |
| Where `SESSION_FAILURES` is assigned, and its value | definition | `harness/curator/runner.py:104`, `2` |
| Where `LOOK_FAILURES` is assigned | does not exist | not found |
| The line of the risk register that defines `R-CONTROL-BLOAT` | rule | `docs/risks.md:64` |
| The line of the glossary that defines Admission | term | `docs/glossary.md:17` |
| Every definition of a function named `refusal` | every definition | `harness/curator/proxy.py:145`, `tools/delegate.py:105` |
| Every line outside the tests that calls `delivery_target` | every caller | `tools/curator_host/live_runner.py:413` |
| Where the class `SessionStore` is defined | definition | `harness/computer/store.py:14` |
| Where `MAX_FRAME_BYTES` is assigned, and to what | definition | `harness/computer/protocol.py:22`, `64 * 1024 * 1024` |
| The file and line that say to reference issues with `Refs #N` | rule | `docs/workflows/work-items.md:66` or `:67` |
| Where a function `resume_admission` is defined | does not exist | not found |
| The line of `role_instruction` in the delegate definitions, and its first six words | term | `.agents/delegates.json:3` |
| Where the class `ViewerProber` is defined | definition | `tests/live_curator_stand_in_run.py:244` |

- **`LOOK_FAILURES`** is the constant an explorer's report cited earlier the same day
  that exists nowhere in the tree
  ([price proposal](2026-11-26-multi-day-standard-build-campaign-freeze-and-price-proposal-968.md)).
  All eleven configurations say it is not found.
- **The key's one gap.** For `refusal` the key held the two Python definitions. Claude
  Haiku 5.5 at High also listed a JavaScript arrow function named `refusal` at
  `tools/curator_host/test/host.test.mjs:424`, which is a definition the lead had
  missed. The key now accepts that line and does not require it; no other
  configuration lists it.
- **`ViewerProber`** is defined in a test file. GPT-6 Luna at Low, Gemini 4 Neon and
  Gemini 4 Hydrogen say it is not found; GPT-6 Luna at High finds it.

## Cost

| Configuration | Wall time | Tokens as the coding agent reported them |
| --- | ---: | --- |
| Claude Haiku 5.5 at Low and High | 17 s and 32 s | 111,000 and 163,000 cached input; 2,400 and 5,700 output |
| Claude Sonnet 5.5 at Medium and High | 18 s and 21 s | 204,000 and 205,000 cached input; 1,600 and 2,600 output |
| GPT-6.1 Terra at Medium and High | 18 s and 19 s | 109,000 and 110,000 input; 450 and 570 output |
| GPT-6 Luna at Low and High | 22 s and 32 s | 191,000 and 109,000 input; 860 and 1,400 output |
| GPT-6.2 Sol at Extra-high | 28 s | 110,000 input; 1,100 output |
| Gemini 4 Neon at High | 355 s | 951,000 input, 3.2 million cached; 34,000 output |
| Gemini 4 Hydrogen at High | 509 s | 2.0 million input, 7.4 million cached; 104,000 output |

Token counts compare within one coding agent only. The Gemini 4 starts have no shell
to search with; the runs do not isolate how much of their time that accounts for.

## What this supports

Every statement is about these fourteen lookups, each configuration as started here
and run once.

- For a lookup with one searchable name, Claude Haiku 5.5 at either effort and GPT-6
  Luna at High answer as exactly as GPT-6.2 Sol at Extra-high, in about the same time;
  GPT-6 Luna at Low misses one.
- Effort does not improve the answers for Claude Haiku 5.5, Claude Sonnet 5.5 or
  GPT-6.1 Terra. GPT-6 Luna misses one lookup at Low and none at High.
- A locator's "not found" is the answer to check: three configurations report a thing
  in a test file as not found, and none invents a location.
- The two Antigravity locators take ten to thirty times the wall time of the others
  and answer 13 of 14.
