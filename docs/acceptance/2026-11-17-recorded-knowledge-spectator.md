---
owner: lead
status: historical
kind: measurement
date: '2026-11-17'
scope: 'Recorded knowledge/public-report reader: retained #642 replay through the real viewer, synthetic current-journal browser acceptance and focused portable checks; no new CDDA play, native build or provider call'
---

# Recorded knowledge in the spectator

## At a glance

The reader for [#689](https://github.com/CVX-Hull/enactive/issues/689) exposes recorded
selection, delivery, explicit reads, verified frozen knowledge and separately labelled
public player reports and mechanical/evaluator results. Its current fields and limits
belong to the [view contract](../contracts/evaluation.md#recorded-knowledge-and-public-reports).
This is reader/interface evidence, not learning benefit, attention/use, qualified
outcome accuracy or human-usability efficacy. No CDDA or SDL fixture process and no provider
request was launched.

## Frozen source and recorded-reader task

The final rendering checkpoint is `7ea9563960e815f1a7f74bf97dce5922d108ea47`;
`e46732f35bccdf62428b738d6c45a28ad4d98a57` is its preceding functional checkpoint.
Later publication adds only this evidence/index metadata.

The read-only catalog used the sealed `delivery-check-642` package and its evaluation
record. A byte-verified disposable evaluation-database copy allowed SQLite to own
its local WAL sidecars; the sealed database was never made writable. This reused the
existing closed historical readers, rather than rebuilding a historical backend.

`probe-real-reader.py` retained the actual `/knowledge` responses. Actor `001`
(`e1f02db82b0542fa82fa609939ba1841`) returned HTTP 200 / 221,378 bytes at a 25-entry
page, with verified **v18**, one briefing selection/delivery and **19 reminder
selections/deliveries**. Actor `002` returned HTTP 200 / 49,100 bytes, verified v18
and one briefing selection/delivery. Counts are grouped by recorded event type and
kind; they are not reads or effects. The first actor's delivered `article-safe-mode-1`
opened from the recorded delivery into that actor's verified snapshot.

The real viewer was served through the existing fixture gateway for browser replay.
**Its control strip, Pause and top image were synthetic fixture data, not a live CDDA
run.** The selected archived run, knowledge responses and linked original PNG came
from the real viewer and retained evidence. No Pause or actor tool was sent.

On the final checkpoint, `render-real-reader.cjs` selected actor 001 and `request-1`,
opened the delivered article by keyboard and confirmed focus on its summary. It then
selected `request-13` and inspected the recorded reminder. The 390 px phone and
1,280 px desktop had zero horizontal overflow and no browser/HTTP problems. An
original-frame link returned HTTP 200 / `image/png`. The lead inspected the retained
phone and current-journal fixture screenshots for readable wrapping, clear labels
and focus. These checks establish the demonstrated reader task, not usability for
all readers or every historical trace.

The v18 coverage has a session but null actor/step, and confirmation records have
session/actor/step ordering tuples. Exact citations and absolute ages remain
unavailable. The retired original historical journal path also remains unavailable;
the page says so rather than claiming zero hints. No private full-store or withheld
unit file was opened to fill a missing join.

## Portable and current-journal evidence

- `.venv/bin/python -m pytest tests/test_viewer_api.py tests/test_viewer_frame.py tests/test_campaign_watch.py tests/test_player_isolation.py -q`: **143 passed**.
- After independent-review fixes, the targeted viewer API/frame rerun: **49 passed**.
- `node --test tests/test_viewer.cjs`: the final complete local suite **9 passed** in
  65.90 seconds. It covers light/dark/390 px views, historical anchors, hint escaping,
  retired programs, the current recorded-reader phone flow, and initially absent
  actors followed by new actors, hints and request IDs without navigation.
- Final fast checks and both source commit hooks passed. Exact protected full CI and
  merged-main checks are recorded on the pull request; no native/gameplay lane is
  claimed here.

The current-journal API/browser cases are **synthetic interface fixtures**. They
separate an explicit knowledge read from computer input, show public intent/cites
and fallible hints, keep operation/SDL receipt dispositions apart from finish claims
and evaluator outcomes, and retain missing data. Cross-run exact anchors, digest
mismatch, absent snapshot hash, read misses and omission counts have focused cases.
The keyboard flow opens the selected entry, script-like text remains escaped, and
switching actor clears the prior entry selection.

## Failures and review dispositions

The first full browser attempt had seven passes and one new-task failure: its CSS
selector assumed that an option value had a literal HTML attribute, while the
browser exposed the value as a property. The next targeted attempt passed refresh
but failed a case-sensitive heading check after CSS capitalized it. Corrected
value/case assertions passed both new tasks, then the final full suite passed.
Both failing logs are retained. An initial replay helper completed the phone task
but assumed request controls survived the existing viewport remount; it now
explicitly reselects the actor for desktop. This is not evidence that local filters
survive theme/viewport remounts.

Independent agent review found two actual issues: the read argument used `id`
instead of current `id_or_title`, and zero-interval loading left new live records
invisible. Both were fixed with successful/missing-read assertions and a changing
browser response at the existing five-second polling cadence. Agent review is not
human approval. The final marker presentation uses named units and outcome labels,
with omissions retained separately, rather than exposing internal JSON formatting.

The viewer reuses the recorded frozen-input digest and existing frame verifier.
R-FALSE-CLAIM/R-EVIDENCE-LOSS are reduced by refusing mismatched snapshot bytes;
R-REGRESSION is covered by the focused reader/gateway/isolation/browser cases.
Cost is one local snapshot hash per selected read and bounded existing test/polling
lanes; no new registry, history store, producer schema, dependency or standing gate
is introduced. Richer belief/scope/ontology/draft views, live curation and causal
benefit remain outside this reader.

## Retention and cleanup

The `recorded-knowledge-spectator` entry in the
[evidence index](../../data/evidence/index.json) retains projected responses, probe
and render scripts, screenshots, failed/passing check logs and review context.
Canonical #642 media remains in its original sealed entry. The local viewer thread
and fixture gateway closed after rendering; source work changed no saves, builds,
shared dependencies or retained experiment evidence. Owned duplicate outputs and
worktrees are retired only after retention/hash verification and protected delivery.

The owned `.runtime/ready-delivery/` duplicate contains 37 files / 4,240,905 bytes
retained under this entry’s `viewer/` directory. It and the isolated
`.runtime/worktrees/delivered-knowledge-spectator/` checkout are retirement targets
after verification; Git and the managed-worktree archive retain source history.
