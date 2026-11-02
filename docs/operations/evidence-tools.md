---
owner: maintainer
review_trigger: Changes to a claim-deciding stage procedure, a tool listed here or a supported contract version
status: active
---

# Evidence tools for claim-deciding stages

A hypothesis test or comparison that decides a claim freezes its inputs, analysis and decision criteria with their hash
before it runs ([S-EVIDENCE](../standards/evidence.md), [evidence cadence](../workflows/evidence-cadence.md)). These tracked
tools are the reusable part of that procedure. The stage's frozen registry, criteria, bindings and outputs are not: they
stay under ignored `.runtime/` and are cited by hash, because a result must be reproducible from its record.

All of them accept only the current contract versions (`campaign-run/5`, `campaign-receipt/2`, `player-driver/6`,
`player-host/6` telemetry 2, `computer-session/3`, `player-memory/1`) and reject anything else with an
`unsupported` error before they write a result. Nothing converts an older format
([S-MIGRATION](../standards/migration.md)); an earlier stage's retained records cite the script that made them by hash
and are not reproduced by these tools. None calls a provider, sends a game input or needs the network.

| Tool | Does | Game or interface binding |
| --- | --- | --- |
| [`tools/stage_driver.py`](../../tools/stage_driver.py) | The serialized, stop-never-retry run loop of a stage: spend accounting that stays an upper bound, caps and balance, state restore or persistent carry, stop rules, provider-side exclusion and cleanup on every exit. Library; the stage supplies its `ports`. | None. Provider, state, build and launch are the stage binding's ports. |
| [`tools/level_stage_analysis.py`](../../tools/level_stage_analysis.py) | The mechanical measures of a level stage from retained artifacts: pass and attempt classes, commit rate with a run-clustered bootstrap, receipt and store cross-checks, custody, refusal circuit breaker and clean-exit inclusion. Decision thresholds come from the stage's frozen criteria file. | The level and recorder lanes of `player-driver/6` and the `player-level/4` store records, named explicitly. |
| [`tools/intent_audit.py`](../../tools/intent_audit.py) | Blind audit packets (session id replaced by an audit id, key held beside the audited directory) and the frozen label table, agreement and reading. It labels nothing itself. | Committed level `replace` records of the current contract. |
| [`tools/sequence_lenses.py`](../../tools/sequence_lenses.py) | Memory depth by leave-one-run-out Witten-Bell log-loss, Lempel-Ziv repetition, recurrence and cross-recurrence, planted-replay power gates. | None; symbols, tokens and distance matrices in, numbers out. |
| [`tools/evidence_stats.py`](../../tools/evidence_stats.py) | Nearest-rank quantiles, run-clustered percentile bootstrap, Cohen's kappa, Gwet's AC1, positive agreement. | None. |

The [testing page](../testing.md) lists what each test file asserts and its limits.

## Run a stage with them

1. **Freeze first.** Write the stage registry and a criteria file (`level-stage-criteria/1`, `intent-audit-criteria/1`)
   and, for a driver, the frozen values `tools.stage_driver.load_frozen` requires. Record their sha256 in the registry
   before any run. `verify_freeze` compares a stage's frozen digests with the bytes now on disk or as committed at the
   frozen source commit.
2. **Bind the driver.** The stage's thin binding in `.runtime` implements the `ports` listed in the `stage_driver`
   docstring (account reading, state, build, launch, watcher, assessment) with the current custodian, usually
   `python -m tools.campaign_run`. Its assessment uses `level_stage_analysis.clean_exit` and `circuit_breaker` for the
   inclusion rule and the stop rule. Only one deciding run is live at a time; the driver never retries.
3. **Analyze the frozen runs.**
   `.venv/bin/python -m tools.level_stage_analysis OUTPUT.json SESSION_DIR... --criteria CRITERIA.json --store-template 'PATH/after-{run}/player.sqlite3'`
   writes `level-stage-analysis/5` (it refuses to overwrite) with the criteria and tool digests beside the measures.
   Without `--store-template` custody and the auditable-record count are reported as undecided, never assumed.
4. **Audit intent, if the stage calls for it.** `python -m tools.intent_audit prepare OUT SESSION_DIR... --store-template ... --context FILE --instructions FILE`,
   then launch the clean-context auditors on the packets only (the lead's procedure, not this tool), then
   `python -m tools.intent_audit summarize OUT --criteria CRITERIA.json`.
5. **Lenses are exploratory.** A lens supports no adoption decision until its planted-effect power check
   (`within_power`, `cross_power`) has passed its pre-registered gate, and it is reported with its negative results.

## Limits

- A mechanical measure is not a gameplay verdict; it counts and classifies what the traces and stores retain.
- The lens statistics are pure Python and O(n²) per run; the numpy implementations that produced earlier lens records
  remain in `.runtime` because numpy is not a project dependency.
- The persistence measures of the #329 persistent stage and the recorder-reliability ladder (#345) depend on their
  stage's registries and on provider calls; they stay with their records until a stage registers them again.
