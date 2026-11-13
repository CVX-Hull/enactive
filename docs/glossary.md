---
owner: lead
review_trigger: A term's meaning changes, or a new term comes into regular use
status: active
---

# Glossary

Each entry says what a term means here; the linked page owns the exact rule. Where pages use one word for two things, the entry names both. "Proposed" marks
a term from the [curated-player design](decisions/009-curated-player.md), which is
not adopted.

| Term | What it is | Owning page |
| --- | --- | --- |
| Actor | One hosted instance of the deciding player in a run. It holds the capability to observe and send input until it finishes or hands off. The curated-player design also uses the word for the playing role. | [Custody contract](contracts/computer-control.md#computer-operations-and-custody) |
| Admission | The package check that lets a finite run start. Also the run that results, numbered within its lineage. | [Campaign procedure](operations/campaign-run.md) |
| Arm | One variant in a comparison, named for what differs. A run package freezes it as an operator label. | [Operator labels](operations/campaign-run.md#operator-labels) |
| Brief | The written instruction a lead gives a delegated agent; it is all that agent knows. An issue's Ready brief is the issue's own description. Older pages also call a change's design summary a change brief. | [Brief template](standards/agents.md#brief-template) |
| CI profile | The set of checks a pull request gets, chosen from its complete diff. | [CI profiles](workflows/ci-profiles.md) |
| Claim | Anything the player asserts. It is fallible data and never grants custody or certifies a save. | [Memory and learning](components/memory-learning.md) |
| Control | A test, check, runtime guard, review or procedure step kept to stop a failure. It is not computer control, the harness's input boundary. | [Controls](controls.md) |
| Curator | A sandboxed coding agent that turns sealed run traces into curated knowledge in short sessions. It holds no custody and does not run in live play. | [Curator](components/curator.md) |
| Custodian | The one process that owns a run's game process, socket, lock, store and single input writer. | [Custody contract](contracts/computer-control.md#computer-operations-and-custody) |
| Custody | Exclusive ownership of the game target and of the right to send it input. | [Run ownership](operations/mission-ownership.md) |
| Deciding player | The model that reads the screen and chooses every game action. | [Player interface](components/player-interface.md) |
| Development run | A finite run on a committed development checkpoint, made to learn about the implementation. It supports no acceptance claim. | [Development runs](development-runs.md) |
| Driver | The program that starts a player host for each actor, keeps the run's limits and verifies a handoff before it starts a successor. | [Player host contract](contracts/player-host.md) |
| Ending reserve (finish reserve) | The part of each run limit held back so that play can end in order. When a limit falls to its reserve, the driver asks the player to finish up. | [Ending reserve](operations/campaign-run.md#ending-reserve-and-external-stop) |
| Envelope | A dollar amount the owner sets for one study; the lead admits runs only inside it. Also: a route envelope is a host's frozen route settings, and a result or error envelope is a message wrapper. | [Budget delegation](operator-permissions.md#finite-gameplay-budget-delegation) |
| Evaluator | Offline code that scores a run from its recorded frames and traces. Its values never reach the player and accept nothing. | [Evaluation contract](contracts/evaluation.md) |
| Finish-up (orderly stop) | An optional, bounded request for the player to wrap up. It never delays Pause or a hard limit. | [External control](contracts/player-host.md#external-control) |
| Handoff | An actor's transfer to a fresh successor within one run. The actor saves a bounded context and is sealed; the driver verifies this before a successor starts. | [Architecture](architecture.md#run-ownership-and-operator-takeover) |
| Held-out lineage | A lineage kept out of design and tuning so that it can test a claim. | [S-EVIDENCE](standards/evidence.md) |
| Knowledge repository (knowledge store) | The curator's Git repository of curated facts, one per game. It is not the player store, the player's own memory database. | [Curator](components/curator.md) |
| Lane | A separate kind of evidence, such as source tests, the compiled adapter or actual play. One never stands in for another. In the hosted check, a lane is also one job. | [Testing](testing.md), [CI jobs](workflows/ci-profiles.md#jobs-of-the-check) |
| Lead, explorer, worker, reviewer | Roles in agent-assisted engineering. The lead owns design, integration and verification. Explorers only read, workers change named paths, and reviewers judge from a clean context. | [S-AGENT](standards/agents.md) |
| Lineage | A chain of admissions that continue one survivor. Separately, a program's lineage is its chain of parent versions. | [Operator labels](operations/campaign-run.md#operator-labels) |
| Monitor | Proposed. A model slot that watches running programs and can only stop them. | [ADR 009](decisions/009-curated-player.md#monitor) |
| Native lane | Evidence from running the compiled adapter against the real game. No fixture replaces it. | [Native acceptance](operations/native-acceptance.md) |
| Outcome, leaf | An outcome is an issue whose child issues carry the work; it owns acceptance. A leaf is one issue for one independently reviewable result. | [Work items](workflows/work-items.md) |
| Owner | The person who owns the project's direction, constraints and money. The charter calls this person the user. | [Charter](charter.md) |
| Owner decision log | The one list of the owner's decisions. | [Owner decision log](decisions/owner-decisions.md) |
| Pause | The permanent stop of automated input for a run, independent of the model. Nothing resumes it, and it neither saves nor quits the game. | [Pause procedure](operations/pause-timeout.md) |
| Player host | The program that runs the deciding player. It owns the model calls, the tool loop and the player's context. | [Player host contract](contracts/player-host.md) |
| Portable check | What `tools/check.py` runs without the native build or the game: structure, documents and the test suites. | [Testing](testing.md#select-checks-from-the-changed-responsibility) |
| Practice instance | Proposed. A one-way copy of the game, forked between admissions, for trials that never become live state. | [ADR 009](decisions/009-curated-player.md#practice-instance-proposal-owner-decision-open) |
| Probe | An offline evaluation question the lead writes from a real episode: at this boundary, a query about X should surface Y. It never reaches the player or the curator. Elsewhere, a probe is a small test call to an endpoint or a host. | [ADR 009](decisions/009-curated-player.md#fitting-and-evaluating-the-ontology-d4) |
| Program | A small JavaScript routine the player saves and runs. It only proposes basic inputs. The curated-player design proposes programs that act in the actor's place. | [Computer-control contract](contracts/computer-control.md#player-knowledge-and-executable-proposals) |
| Receipt | A record of what actually happened: a delivery receipt for each input, and a run's final `receipt.json`. Neither accepts gameplay. | [Start and close](operations/campaign-run.md#start-and-close) |
| Record | A dated record is a page under `docs/acceptance/` for evidence a diff cannot hold, such as a run or a study result. A player record is one entry in the player's memory. | [S-DOCS](standards/documentation.md#current-pages-records-and-decisions) |
| Re-observation, rediscovery | A re-observation is the player seeing again something it already observed. It is a rediscovery when the fact was known before a boundary: a handoff or a new admission. | [ADR 009](decisions/009-curated-player.md#evaluation-and-studies) |
| Risk | A failure that can realistically happen within the project's scope of use. | [Risk register](risks.md) |
| Run ledger | The tracked file `data/evaluation/runs.jsonl`: one row for each admission, with its attempts, time and spend. | [Evaluation contract](contracts/evaluation.md#tracked-run-ledger-and-metrics-snapshot) |
| Run package (frozen package) | A fresh directory whose manifest fixes everything one run uses, from source commit to spend limit. It is used once. | [Frozen data](operations/campaign-run.md#frozen-data) |
| Sealed evidence store | The read-only store that holds the raw evidence dated records cite. | [Evidence retention](operations/evidence-cleanup.md) |
| Session | One fresh run directory with its store. A curator session is different: one short sandboxed curator run. | [Computer-control contract](contracts/computer-control.md#responsibilities-and-current-data) |
| Snapshot | The immutable context an actor saves at handoff. In the curated-player design, a published version of curated knowledge. The metrics snapshot is a tracked file of evaluator headlines. | [Custody contract](contracts/computer-control.md#computer-operations-and-custody) |
| Source | One captured game image, kept with an ID and a hash. A click names a source issued to that actor. | [Custody contract](contracts/computer-control.md#computer-operations-and-custody) |
| Spectator | What a person watches a run through: a control path with the frame, status and Pause, and a read-only viewer of evaluator views. | [Observer operations](components/observer-operations.md) |
| Spend limit | The most dollars one run may count as spent, declared in its package. The player host stops the run at it. | [Spend limit](operations/campaign-run.md#spend-limit) |
| Unit | In a study, the coarsest thing that shares no state: a run, or a lineage when runs share memory. It is the sample size. The curator memory study also counts smaller scoring units. | [S-EVIDENCE](standards/evidence.md) |
| Working set | Proposed. The part of curated knowledge put in front of the actor: open commitments, relevant facts and hazards. | [ADR 009](decisions/009-curated-player.md#reaching-the-actor-without-latency-d2) |
