---
owner: lead
status: historical
date: '2026-11-13'
scope: 'Four owner decisions on controls left open by the 12 November 2026 control review, and what was changed for each: the research-source rules, the standing cumulative spend cap, one unreadable sealed session, and the adapter test that hung without its packages (#556, #557)'
---

# Remaining control decisions, 13 November 2026

The [control review](2026-11-12-control-review-and-names.md) left several candidates
for the owner. The owner answered four of them through the question tool; each answer
is quoted. The decisions are also on
[#556](https://github.com/CVX-Hull/enactive/issues/556) and
[#557](https://github.com/CVX-Hull/enactive/issues/557).

| Question | Decision | What changed |
| --- | --- | --- |
| The rules for research write-ups in the evidence standard: tag what was read and when, flag sources older than 18 months, take claims about models only from dated primary sources, keep current sources out of briefs | "Keep one rule" | [S-EVIDENCE](../standards/evidence.md) keeps the rule that claims about models and providers come from dated primary sources read for the task. The tagging, the 18-month flag, the reading checklist for method papers and the restriction on briefs are removed. No failure was recorded behind them, and they cost time on every research task |
| The standing $1,000 cumulative cap across studies, whose running total was kept by hand and was out of date | "Key limit replaces it" | [Operator permissions](../operator-permissions.md) states that the OpenRouter key's credit limit is the one overall cap. The cumulative cap and its hand-kept total are gone. Each study still needs its own envelope from the owner, and each run its own dollar limit |
| One sealed session, `lh4a1`, that cannot be evaluated from the evidence store | "Record it as a limit" | The [evaluation contract](../contracts/evaluation.md) states that this session's database cannot be opened inside the read-only store, because it was sealed in write-ahead-log mode without its log files. The sealed copy is untouched, and the closed index still lists 54 sessions |
| The player-host adapter test, which hung for six minutes and left processes behind when the host's Node packages were not installed | "Yes, fix it" | The test fails at once, naming the install command, when the packages are missing. On a timeout it now stops the whole process group, so the per-file Node processes do not outlive it. That was the cause of the processes two workers left behind on 12 November |

Also changed with these, as cleanup the review had listed: a memory cut-off parameter in
the trace projection that no caller passed any longer is removed.

## Evidence

- With the host's packages moved aside, the adapter test failed in under a second with
  the install message; with them restored it passed in 17 seconds.
- The full local check passed on the change.

## Limits

- Research pages written under the earlier rules keep their source tables and recency
  notes; they describe what was done then.
- The key's credit limit is set by the owner outside the repository. The code cannot
  read it, and nothing here checks it.
- Spend outside the four studies in the run ledger is stated only in the dated record of
  the work that spent it; no total across them is kept.
