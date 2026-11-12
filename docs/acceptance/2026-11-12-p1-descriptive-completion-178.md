---
owner: lead
status: historical
date: '2026-11-12'
scope: 'Completed owner-amended P1 measurement, descriptive comparison and coding-host robustness (#178)'
---

# P1 descriptive completion

P1's registered outcome is **no-go: repeat 2 reached its historical cap**. That
failure remains permanent. The owner-funded recovery completed the measurement
for discussion; it does not restore a registered pass or authorize live adoption.

The complete descriptive comparison finds lower measured recall for curator B:
**13/89 units in each repeat (14.6%), against A's 18/89 (20.2%)**. The pooled
B-minus-A difference is **−5.62 percentage points**. The fixed Audit sample contains
fewer contradicted or outdated B items: **1/40 and 2/40**, against A's **29/40**.
This is an observed retention/staleness tradeoff in the amended offline corpus,
not evidence that B meets the frozen benefit criterion.

The exact frozen [`p1-result/1` result](assets/curator-memory-study-178/result.json) is
guard-only. The separate [`p1-description/1` report](assets/curator-memory-study-178/description.json)
contains the complete, unchanged descriptive calculations. The
[metadata and supplementary aggregates](assets/p1-descriptive-completion-178.json)
define `p1-descriptive-completion/1`: source/input hashes, context accounting,
reported usage and the protocol's descriptive breakdowns. It adds no decision rule.

## Measured outcomes

Recall means a reader, given one delivered text and a frozen question about an
earlier frame, supplies an answer that the blinded grader accepts against the
key. It measures this fixed set of re-observed information, not all game knowledge
or live gameplay performance. There are 89 units, 73 information clusters and 224
listed probes under the unchanged selection rule.

| Arm | Correct / units | Recall | Undelivered units / game hour | Contradicted or outdated Audit pairs | One-sided 95% upper bound |
| --- | ---: | ---: | ---: | ---: | ---: |
| A1 | 18/89 | 20.2% | 0.9089 | 29/40 (72.5%) | 83.7% |
| B1 | 13/89 | 14.6% | 0.9729 | 1/40 (2.5%) | 11.3% |
| B2 | 13/89 | 14.6% | 0.9729 | 2/40 (5.0%) | 14.9% |

The mean difference and each repeat's difference are −5/89. The frozen cluster
bootstrap's one-sided 97.5% lower bound is −11.24 points. The +15-point superiority
criterion fails; the only lineage with at least 20 units, lh4, is also below A.
The observed negative difference is not presented as a new test of significant harm.

Audit rates apply to the fixed sampled item-boundary pairs, 40 per arm/repeat.
The criterion includes claims that had stopped being true by the last listed
frame. These percentages are not population-wide hallucination rates. Both B
repeats satisfy the original false-fact guard; repeat 2 fails the conservative
cost comparison, and the historical cap already fixes the registered outcome.

## Controls and descriptive breakdowns

Reference R is correct on 12/89 units (13.5%). A exceeds R by 6/89, or 6.74 points,
as a descriptive comparison. Both positive controls, PW and PP, score 89/89; no
paraphrase failed twice. The seeded rejudge reproduces all 54 labels, including
all 11 answered-either cases: agreement and kappa are 1.0. The generated
`robust_to_rejudging: false` means the benefit criterion still fails after label
substitution; it does not mean the repeated labels disagree.

The bias control has only 12 Reference-correct units, below its minimum of 20.
Its inactive flag is not evidence that bias is absent.

| Lineage | Units | A correct | B1 correct | B2 correct | R correct |
| --- | ---: | ---: | ---: | ---: | ---: |
| lh1 | 11 | 2 | 2 | 2 | 2 |
| lh2 | 7 | 2 | 2 | 2 | 2 |
| lh3 | 9 | 3 | 2 | 2 | 2 |
| lh4 | 62 | 11 | 7 | 7 | 6 |

Together lh1–lh3 have 27 units: A 7, each B 6 and R 6. Lh4 has 62 units: A 11,
each B 7 and R 6. This concentration limits any lineage-wide generalization.

| Boundary kind | Units | A correct | B1 correct | B2 correct | R correct |
| --- | ---: | ---: | ---: | ---: | ---: |
| admission | 36 | 7 | 4 | 4 | 4 |
| handoff | 53 | 11 | 9 | 9 | 8 |

Boundary kinds use the maintained `boundary_kind` contract. These group counts
and the token table below are descriptive; they do not change the primary rule.

## Delivered working-set tokens

Counts use the frozen approximation ceil(UTF-8 bytes / 4), not model tokenizer
measurements. All 23 boundaries are complete. Zero B counts are recorded empty working sets,
not missing replay rows. R has no produced working set; its zero placeholder is
not a measurement of received-text length and is excluded from this table.

| Arm | Total | Mean / boundary | Median | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| A1 | 27,879 | 1212.1 | 1267 | 416 | 1980 |
| B1 | 30,654 | 1332.8 | 1909 | 0 | 1999 |
| B2 | 31,264 | 1359.3 | 1784 | 0 | 1999 |

| Lineage | Boundary | Kind | A1 | B1 | B2 |
| --- | --- | --- | ---: | ---: | ---: |
| lh1 | `lh1a1-001>lh1a1-002` | handoff | 416 | 0 | 0 |
| lh1 | `lh1a1-002>lh1a2-001` | admission | 416 | 1390 | 1174 |
| lh1 | `lh1a2-001>lh1a3-001` | admission | 416 | 1963 | 1784 |
| lh1 | `lh1a3-001>lh1a3-002` | handoff | 872 | 1963 | 1784 |
| lh2 | `lh2a1-001>lh2a1-002` | handoff | 484 | 0 | 0 |
| lh2 | `lh2a1-002>lh2a2-001` | admission | 484 | 940 | 1044 |
| lh2 | `lh2a2-001>lh2a2-002` | handoff | 1131 | 940 | 1044 |
| lh3 | `lh3a1-001>lh3a1-002` | handoff | 524 | 0 | 0 |
| lh3 | `lh3a1-002>lh3a2-001` | admission | 524 | 737 | 1081 |
| lh3 | `lh3a2-001>lh3a2-002` | handoff | 939 | 737 | 1081 |
| lh4 | `lh4b1-001>lh4b1-002` | handoff | 630 | 0 | 0 |
| lh4 | `lh4b1-002>lh4b2-001` | admission | 1267 | 1145 | 1274 |
| lh4 | `lh4b2-001>lh4b2-002` | handoff | 1877 | 1145 | 1274 |
| lh4 | `lh4b2-002>lh4b3-001` | admission | 1980 | 1909 | 1999 |
| lh4 | `lh4b3-001>lh4b3-002` | handoff | 1717 | 1909 | 1999 |
| lh4 | `lh4b3-002>lh4b4-001` | admission | 1740 | 1998 | 1971 |
| lh4 | `lh4b4-001>lh4b4-002` | handoff | 1518 | 1998 | 1971 |
| lh4 | `lh4b4-002>lh4b5-001` | admission | 1837 | 1962 | 1977 |
| lh4 | `lh4b5-001>lh4b5-002` | handoff | 1733 | 1962 | 1977 |
| lh4 | `lh4b5-002>lh4b6-001` | admission | 1733 | 1999 | 1973 |
| lh4 | `lh4b6-001>lh4b6-002` | handoff | 1960 | 1999 | 1973 |
| lh4 | `lh4b6-002>lh4b7-001` | admission | 1845 | 1979 | 1942 |
| lh4 | `lh4b7-001>lh4b7-002` | handoff | 1836 | 1979 | 1942 |

## Costs and finite allocation

| Repeat | Recorded curator debits | Separate unresolved allowance | Conservative scoring amount | Actor denominator | Ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| B1 | $20.28442860 | $0 | $20.28442860 | $59.33655440 | 0.341854 |
| B2 | $50.80594130 | $11.90480270 | $62.71074400 | $59.33655440 | 1.056865 |

These are best-effort recorded debits and a separate allowance, not an invoice.
The separate pilot/development curator debit is $26.94660320. Historical failures,
qualification overhead and the cap flag remain. No browser reconciliation was
required and no new OpenRouter/curator call was made in this measurement recovery.

The corrected chain used **846 contexts / 856 reserved of 1,000**. Its final
approved complete-input recovery used **102 of at most 145**; 43 unused slots
are retired. Ten older unused reservations remain counted. The valid older
Audit-001 context is retained separately, not rerun or charged as a new context.

| Corrected-chain stage | Actual contexts | Reservations |
| --- | ---: | ---: |
| Grounded development | 162 | 163 |
| Held questions, screen and paraphrase chain | 45 | 45 |
| Original first readers | 534 | 534 |
| First redo wave before second refusal | 3 | 12 |
| Complete-input remaining readers | 10 | 10 |
| First graders | 25 | 25 |
| Seeded rejudge readers | 54 | 54 |
| Rejudge graders | 2 | 2 |
| Remaining original Audit redos | 11 | 11 |
| Total | 846 | 856 |

All 846 corrected-chain contexts have a completed usage receipt: 92,790,125
reported input tokens, including 77,708,672 cached input tokens, and 296,163 output
tokens. The separate reported reasoning-output counter is 30,679; it is not added
again to make a token total. Existing credits are **unpriced, not zero**. These
counters exclude older unqualified studies and lead/reviewer work. Whole-workflow
labor and dollar cost remain unknown.

## Robustness, source and admission

The [owner approval](https://github.com/CVX-Hull/enactive/issues/178#issuecomment-6826313984)
preceded PR #551's merge as `19edb7f`. Its tree equalled reviewed `c14c59c`.
[Full PR CI](https://github.com/CVX-Hull/enactive/actions/runs/43175809992) passed
1,480 tests and 232 subtests; [actual-main structural CI](https://github.com/CVX-Hull/enactive/actions/runs/43237279067)
passed before dispatch. Measurement-host runtime source remained `13bb21d`; analysis and batch
builder bytes remained the frozen `91546ec…` and `d819933…` files. The question
digest is `8fa6aec4d19efa9605005075bad8db8d2e72f4a8af04a46b0e03c85797556e66`.

Every remaining role received complete public batch JSON as initial text. Visual
roles retained exact original PNGs with native path/ordinal markers and verified
count/order/bytes. Subset preparation avoided copying unused batches. Cleanup has
one owner per child and guards signal reentry. Forty-six focused host tests,
actual local payload rendering and the protected full profile are separate
supporting lanes; they do not establish new native game or graphical acceptance.

Ordinary installed CLI 0.167.1, `gpt-6.1-sol/high`, fresh ephemeral contexts,
maximum concurrency three and 900 seconds per context were retained. No dedicated
binary, new dependency, copied-image cache or global installation/profile change
was needed. Compatible CLI updates remain allowed after local input rechecking.
The [host map](../operations/coding-agents.md) supports both coding agents through
shared `AGENTS.md` instructions and host-specific mechanics. Current project MCP
autoload files are absent; an engineering player adapter still requires an
explicitly issued actor. No game input or actor was created here.

Accepted first-reader outputs are 522 valid originals, two valid earlier redos
and ten complete-input recoveries. Original-key parsing gives 534 answers and
534 fresh labels, then exactly 54 seeded rejudge answers/labels. The independent
valid Audit-001 and eleven original unused redos parse to 120 rows. Together with
eight unchanged cost rows, the **716-row input was frozen and independently
accepted before efficacy scoring**. Refused and old question-dependent data remain
excluded and retained. No result-dependent resampling or output selection occurred.

Finite inert reviews resolved presentation formatting, literal path aliases,
Python JSON/file mechanics and successful same-context HTTPS fallback. Original
reports and failed helper diagnostics remain. Audit005 reread only its newly
written answer inside a line-count assertion; no readback content entered its
judgments. The lead and independent reviewer accepted this as authorized writing
verification under the approved prompt/protocol. The older host page's literal
batch/images read whitelist was overly narrow, so no literal-whitelist pass is
claimed; its wording is clarified after all scientific contexts ended. This adds
no external input, earlier answer or new model inference.

## Limits and next decision

There are only four independent lineages; the within-lineage cluster bootstrap
understates between-lineage uncertainty. Scope is one game, S1 start scenario,
actor model and route, with pre-emission traces from two player versions. Offline
delivery does not establish that a live actor would use the information. The
[frozen limitations](../design/p1-study-3.md#limitations) continue to apply.

Questions were replaced after replay under an explicit owner amendment. The
result is descriptive only, with the permanent registered cost-guard failure.
Delivery/context formatting changed after measurement began; the valid earlier
development qualification was retained without claiming format equivalence.
Rejudge variation could include format variation even though this sample agreed.
The Audit is not blind by construction. Semantic judgments are model-based;
controls and repeat agreement do not certify human ground truth. The previously
disclosed operator-exposure limits remain, so strict observer blindness is not
claimed. Presentation, path checks and group snapshots establish neither
attention, provider receipt, generic JavaScript/Python safety nor OS confinement.

Keep the curator gated. Development work should examine retention choices and
publication timing while preserving the lower observed staleness in the Audit.
Any renewed benefit claim needs a fresh prospective protocol and owner decision;
these completed data cannot be turned into a registered pass. There is no live
adoption or further paid run authorized by this record.

## Evidence and publication

Raw questions' production traces, reader/curator content, screenshots, candidates
and all failures stay private. Git contains only the three approved question
files, source, metadata and aggregates. The private corpus is sealed read-only as
`p1-grounded-completion-178`: **10,250 files, 65,349,350 bytes**. Its
[manifest](../../data/evidence/p1-grounded-completion-178.sha256) SHA256 is
`281054d18cbe95569bcd1b838505aac716d393708bad8fd8328ebed5ad796798`;
[indexed origins](../../data/evidence/index.json) map `correction/`,
`complete-input/` and `checks/` to the original stage folders. Full-store verification
passed for every hash before duplicate retirement. Original screenshots and the
earlier replay/cost inputs, including retained Audit-001, remain in their original
sealed families. There is no off-machine backup.

**Retirement, 12 November.** After checking every source against its sealed path and
hash, the lead removed 10,193 duplicate files (64,885,225 bytes) from
`.runtime/p1-grounded-correction-178` and the worker's
`.runtime/p1-initial-text-recovery-178`. Only 26 empty excluded lock stubs remain
there; none is live authority. The existing `529-answer-key` checkout is retained:
the app inventory reports no managed worktree attachment, so its ownership cannot
be verified for archival. No source checkout was forcibly removed or dedicated
CLI/image copy created. The [environment inventory](../environment.md) records
these residuals. Check logs held by the new seal remain regenerable routine copies.

The pre-score freeze and original score command logs are in `complete-input/`.
Rescoring uses their recorded inputs rebased through the indexed origins into this
store and the earlier sealed families; retired paths are provenance, not aliases.
Protected report PR/main validation and the exact accepted head are recorded on
[#178](https://github.com/CVX-Hull/enactive/issues/178).
