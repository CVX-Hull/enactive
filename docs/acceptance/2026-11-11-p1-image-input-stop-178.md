---
owner: lead
status: historical
kind: study
date: '2026-11-11'
scope: 'P1 recovery-7 completion and the pre-scoring discovery of missing Question image input, refused Audit outputs, bounded image-delivery repair and pending measurement correction (#178)'
---

# P1 replay completed; image-input verification stopped measurement

The approved curator recovery completed, but **P1 has no qualified efficacy result**.
Before scoring, a trace audit found that the development and held-out Question
writers had received batch text without the required screenshot input. Their
questions and all dependent measurement are retained, unqualified and unscored.
This does not establish that every question or key is wrong. It establishes that
the required grounding was not verified. Earlier format and freeze checks missed
this input-delivery failure.

The [registered cost guard already failed](2026-11-11-p1-cost-guard-178.md) and stays
failed. Additional funding or repaired measurement cannot produce a registered go.
The [correction proposal](../design/p1-study-3.md#approved-image-grounding-correction)
requires a new owner decision because the approved completion kept scientific
questions unchanged. No further model dispatch or live adoption is authorized by
this record. [#178](https://github.com/CVX-Hull/enactive/issues/178) owns that decision.

## Completed curator recovery

The [owner's $36 decision](https://github.com/CVX-Hull/enactive/issues/178#issuecomment-6809496657)
preceded [PR #548](https://github.com/CVX-Hull/enactive/pull/548)'s merge and dispatch.
[Full CI](https://github.com/CVX-Hull/enactive/actions/runs/43117288969) passed:
1,434 tests, 50 skipped, 232 subtests and eight warnings. Reviewed head and
`d6d5104f13e78d42ab84952d606c17a179a9be07` have identical trees;
[actual-main structural validation](https://github.com/CVX-Hull/enactive/actions/runs/43118760077)
passed before execution.

Runtime remained `adc9c8cc292f461fcee36f612db53dc27d9324c8`, with canonical arms
SHA256 `bf144eaeae72454da024d6a819600c6e1b30c0e1ac4043fd713ec2864e496daa` and
retained-plan SHA256 `5caa17500a7f653a17f4373100e8f407f8afe7813f16d6c6bcb015f020fdcd69`.
R1, R2 LH1 and eight sealed admissions remained; only fresh LH4b5–LH4b7 ran.
Each retained 120 attempts, 30 minutes and $12, GPT-6.1 Terra/medium and the pinned
OpenRouter–OpenAI route. No model, route, price, scientific brief or question changed
while it ran.

| Fresh admission | HTTP200 attempts | Debit, USD | Outcome |
| --- | ---: | ---: | --- |
| LH4b5 | 39 | 1.54580885 | Sealed, one accepted submission |
| LH4b6 | 48 | 1.88784865 | Sealed, one accepted submission |
| LH4b7 | 40 | 1.65604380 | Sealed, one accepted submission |
| Total | 127 | 5.08970130 | Complete, uncapped, fully settled |

No new missing usage, refusal, breach, revocation or unsettled accounting remained.
Owned processes stopped, writable workspace/draft/archive/staging state cleared,
and unused lazy directories were absent. Publication advanced v4→v7. Independent
checks retained 68 original fingerprints and all eleven selected receipt identities.
Maintained delivery produced 92 complete rows: 23 boundaries for A, Reference, B1 and B2.
The [terminal metadata receipt](assets/p1-recovery-7-complete.json) records hashes,
settlement and cleanup without scientific text.

R2 recorded debits are **$50.80594130**, with the separate earlier **$11.90480270**
allowance: **$62.71074400** conservatively, against the unchanged **$59.33655440**
actor denominator. R1 is $20.28442860. All failures and qualification remain counted
once; retained selection costs are not charged again. Unused **$30.91029870** is retired.
The eight cost rows retain R2 LH4's historical cap flag. These are best-effort debits
and allowance, not a reconciled invoice; historical tier/billing uncertainty remains,
with no browser requirement. Pilot/development's $26.94660320 is separate.

## Measurement failure and its extent

On frozen measurement source `d6d5104`, ordinary Codex CLI 0.167.1 on
`gpt-6.1-sol/high` returned 534 first-reader outputs, 26 first-grader batches,
54 seeded rejudge outputs, one rejudge-grader batch and 12 Audit batches.
Their maintained parsers accepted 534 + 54 labels and 120 audit rows. Immutable
batch/prompt/input hashes passed. That proved output shape and lineage, not image
exposure or scientific validity. No score or arm comparison was computed or inspected.

Independent tool-trace review then found incomplete image presentation for **every
item in all twelve Audit batches**. Five sessions had no pixel-read operations.
Other sessions attempted viewing but had partial, rejected or truncated transport;
72 image payloads carried explicit truncation markers and failed strict base64 decoding.
Valid original-PNG payloads covered 161 of 339 named frames in one batch and 11 of
441 in another; no item had its complete named-frame set presented. All twelve
outputs were uniformly process-refused before labels or scores were examined.

The Audit brief asks for comparison against listed frames; it does not literally
say "view every image". Requiring complete input presentation was an explicit,
label-independent implementation of the intended evidence delivery. Presentation
still cannot prove attention or correct interpretation. Traces are not a complete
OS-access audit and do not establish filesystem confinement.

The dependency audit found the earlier Question failure independently of this
truncation incident:

| Question chain | Sessions | Initial items | Rewrite items | Recorded image exposure |
| --- | ---: | ---: | ---: | --- |
| Held-out | 13 | 89 | 33 | None |
| Current development calibration | 3 | 20 | 9 | None |

Both stage manifests record CLI **0.167.0** and bind launcher SHA256
`d8aeaf90218ea4e51c9b0182c134fb1a4500506e8b4b656a7da1ce8b0e59e080`.
That launcher attaches no initial images. All sixteen completed traces show only
batch reads and answer writes, with no image tools, pixel reads or image payloads.
Consequently neither Question chain establishes the required screenshot grounding;
the old development calibration cannot qualify corrected held-out measurement.
Earlier probe-Confirmation exposure is **unknown**, not failed: fifteen retained
batch files hold 224 pairs and 448 PNG references, but execution traces were not found.
No probe membership or question was changed to address that uncertainty.

The [incident metadata](assets/p1-image-input-incident-178.json) binds counts,
question/launcher hashes, the stop and accounting. Original questions, returned
answers, failed attempts and provisional parsed rows remain intact and excluded
from final efficacy scoring. The lead remains blind to scientific content and labels.

## Repair evidence and remaining gate

The protocol's existing one-redo rule authorized one fresh original Audit batch
following process refusal. A finite driver supplied only the exact original PNGs
listed by that batch using initial `--image` attachments. Local
[Codex prompt rendering](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
verified all twelve batches' 4,120 image payloads byte-for-byte without inference;
no image copies, edits, montages, OCR or extra data were introduced.

Independent review found controller-interruption cleanup and admission/stop races;
they were fixed before the redo. Two real owned-process fixtures passed: a stubborn
descendant was killed even after its leader exited, and actual parent SIGTERM
closed the owned group. A hard kill or a process escaping its owned group remains
outside that cleanup assurance.

Only Audit-001's permitted redo ran: 354 exact original attachments, ten valid
candidate rows, no retry, no observed foreign-file/network/other-agent operations,
and verified group exit. Non-null frame IDs belonged to each item's listed sources.
It remains a candidate, not a final scientific result. Its 1,308,614 reported tokens
are not an invoice. First held measurement plus this redo reports 81,333,135
input/output tokens, including cached tokens and the refused audit attempts;
this is not a complete study-cost or labor measurement. The remaining eleven redo
allowances have not been used. No further model call followed the Question finding.

The maintained [input boundary](https://github.com/CVX-Hull/enactive/blob/08c8f7aa902a0fe45c3aad22a6b29a41677336fc/tools/coding_host/p1_input.py) and bounded executor
replace reliance on agents voluntarily opening image paths. They preserve role
information boundaries, bind expected key/source/CLI/input hashes, and verify exact
role-appropriate rendered images before inference. Text-only roles receive none.
Local checks on actual Question, Audit and Reader batches verified 10, 354 and zero
images respectively with no inference. Executor preparation additionally verified
all nine original Question batches and all 89 image attachments without inference.
The final focused suite passed 29 tests, including actual controller SIGTERM of an
owned local fixture group. The reviewer's sandbox run passed its control assertions
but could not run `ps`; the authorized outside-sandbox rerun completed the liveness
checks. No passing mock replaced that unverified lane. Synthetic source tests and owned-process
fault checks are separate from scientific qualification; neither validates questions
or proves live gameplay benefit.

The next step is the owner's decision on the proposed fresh, image-grounded
measurement chain. It retains the completed curator replay, frozen units and all
historical failures; it does not spend more through OpenRouter or relax the cost
failure. A failed qualification stops rather than tuning on held-out outcomes.

## Sealed evidence and duplicate retirement

The private study is sealed read-only at `.runtime/evidence/p1-image-input-stop-178/`:
**11,544 files, 159,086,058 bytes**, manifest SHA256
`bc47a8c2746c8b619c5bd653db3b702be24d61b2894c6a0075746a2223ecd1cd`.
The tracked [manifest](../../data/evidence/p1-image-input-stop-178.sha256) and
[evidence index](../../data/evidence/index.json) map source parts and availability.
All prior campaign seals remain; their images were referenced rather than copied.
Storage-checkout origins are not execution-source claims: retained stage records
keep actual freezes and mixed-source lineage.

Full-store hash verification passed. Every original evidence file then matched the
seal by path and bytes before its duplicate was removed. The
[retirement receipt](assets/p1-image-evidence-retirement-178.json) lists the twelve
runtime directories and two checker-log files retired; only non-evidence bytecode
cache was excluded. Source checkouts, dependencies, saves, prior campaign images
and canonical tracked question files were not removed. No raw scientific content
was published. Future correction must read archived inputs from these sealed parts,
not assume the retired source paths still exist. The store has no off-machine backup.

## Protected CI boundary finding

The first [full PR run](https://github.com/CVX-Hull/enactive/actions/runs/43136398358)
failed the existing host-neutrality check: 1,462 tests passed, one failed, 50 were
skipped, 232 subtests passed and eight warnings remained. All 29 new executor/input
tests, including Linux process fixtures, passed. The code had been placed in generic
tooling and the protocol named CLI-specific commands. The repair moves both adapters
into the explicit `tools/coding_host/` boundary, migrates every import/command/link
without compatibility aliases, and keeps implementation details on the host page.
The guard retains generic tooling/design restrictions and recognizes this named
adapter boundary beside the existing player and curator adapters. The failed run is
retained; exact-head protected CI must pass before the owner decision and merge.

Compatible CLI updates are accepted after exact local input re-verification, with the
observed version and receipt digest recorded per attempt. Code/model/effort, key,
prompt and image bindings remain; a missing version is rejected. Completed candidates
are not rerun merely because the installed CLI changed. This applies the owner's
version direction without a binary copy or repeated calibration.
