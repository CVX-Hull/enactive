---
owner: lead
status: historical
date: '2026-11-19'
kind: run
scope: 'One approved Campground start ended after the first menu observation with no verified survivor or eligible memory decision'
---

# Campground setup ended after the first menu observation (#799)

## At a glance

The only rendered view in the initial admission showed the New Game submenu with Preset Character highlighted and Custom Character listed above it. The player never established the assigned world or survivor. The record contains no ordinary Save to title or separate Quit, natural wake, game clock, delayed resource choice or scored effect. Each provider attempt returned a price. The unused study authority expired.

## Scope and evidence

The owner approved the [#797 package](https://github.com/CVX-Hull/enactive/issues/797) for one Wilderness / Campground / Survivor world with up to five conditional serial reloads and a $90 envelope. The player used the ordinary pinned OpenAI Standard GPT-6.1 Terra route through OpenRouter with medium effort, full context and normal knowledge, journal and handoff. One native lane ran against clean main `7a9579726776c8459f912c9829978cb6c5ff76d1`. The initial manifest SHA-256 was `cb67cccd122639478c675083d22ca9a6bde00ed043a71264300984ab8c3ec87a` and the approval inventory SHA-256 was `d8012ee6be040e49dfc87f392fd5762ca39c1f4024bb085d31ccbe21ce52f1e4`. Preflight passed again after installing the verified four-file configuration-only start.

| Observed event | Evidence and interpretation |
| --- | --- |
| Initial observation | Source `d16ea238c2794897a7839549df297a69-2` depicts the character submenu. The next request included this image. No world, survivor or clock is visible. |
| First input | The player stated an intent to check for an existing survivor before starting setup. In one batch it sent Escape, Right and Enter. Native receipts record two delivered actions. The third action has unknown delivery after the native connection ended. No intervening screen was captured. |
| Collection and ending | The player collected the original operation `eec1b51e056e48888af8339d5ad7a0b4`. Its status remained unknown. A subsequent observation was refused by the input fence. The actor reported that it could not continue. The native process exited with code zero before forced signals. Which menu transition occurred and what caused that exit remain unknown. |
| Study eligibility | A separate reader reconstructed the player cutoffs in order from the first observation through the direct finish. No world-specific resource, competing option, cutoff or effect qualified. There was no target to look up and no measurement of memory efficacy. |

The ledger accounts for both player and recall usage. No player inference timed out or retried, so the run supplied no live test of the [#795 stream recovery](https://github.com/CVX-Hull/enactive/pull/798). There were no operator game inputs or reloads. The [run ledger](../../data/evaluation/runs.jsonl) and [metrics snapshot](../../data/evaluation/run-metrics.jsonl) retain the admission and measured quantities. Use the sealed journal and original run basename to reproduce the evaluator record.

## Custody and disposition

The supervisor verified closure. The lead checked all six owned process groups absent, all three loopback listeners closed, and the shared game lock idle. The maintained restore operation archived the nine-file study userdir and returned the original 82 files with identical content hashes. The [sealed evidence index](../../data/evidence/index.json) binds the original admission, configuration-only archive, study userdir, operator approval, working ledger, evaluator and chronological coverage to this record. After full hash verification, the lead retired the duplicate run directory, operator working directory, configuration-only staging archive and closed study-userdir archive. The displaced original recovery archive remains available.

The offline follow-up compares the first decision against successful Campground setup and distinguishes fresh-start instructions from a handoff's continuity check. The evidence cannot establish whether a different choice would have produced an eligible delayed decision. [Setup follow-up #800](https://github.com/CVX-Hull/enactive/issues/800) · [Acquisition #799](https://github.com/CVX-Hull/enactive/issues/799).
