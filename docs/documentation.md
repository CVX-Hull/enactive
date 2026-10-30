---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Documentation: understand, decide, implement, verify

Start with the [overview](overview.md), then the responsibility you need to
challenge. [S-DOCS](standards/documentation.md#s-docs-useful-maintained-documentation)
owns documentation requirements. The lead maintains navigation with component
maintainers. Deciding players use the [compact guide](player-guide.md), frozen
assignment and actual tool schema; routine play does not require engineering history.

![Current review hierarchy from purpose through contract and implementation.](diagrams/architecture-review.svg)

This current logical diagram answers “Where should review begin?” Arrows show
constraint or drill-down; boxes are document roles, not separate processes or
approval stages. [Editable source](diagrams/architecture-review.mmd).

## Read at the level of your question

| Question | Start | Follow when needed |
| --- | --- | --- |
| Purpose and constraints | [Charter](charter.md) | [Engineering standards](engineering.md) |
| Product capability and limits | [Overview](overview.md) | [Architecture](architecture.md) |
| Ownership, state and failures | A component linked from architecture | [Current exact contract](contracts/computer-control.md), code and assertions |
| Operate a finite run | [Setup](setup.md), [runbook](runbook.md) | [Campaign procedure](operations/campaign-run.md) |
| Change scope and acceptance | GitHub Issue/PR | Affected parent/component, contract and [review policy](workflows/review.md) |
| Evidence and remaining work | [Work](work.md) / public Project | Dated original report and artifacts |
| Checks and their limits | [Testing](testing.md) | Shared [CI selection](../tools/ci.py) and actual assertions |

Architecture starts outside a responsibility, then explains owned state,
interfaces, important flows, failures and limits. Decompose only where a concrete
reader task or boundary benefits; no universal file-size quota applies.

## Repository boundaries

| Location | Responsibility |
| --- | --- |
| `harness/computer/` | Mechanical packets, socket, writer, store, target custody and SDL adapter; no game/player semantics. |
| `harness/player/` | Pure fallible knowledge, image views, bounded programs and context; no process/provider/native authority. |
| `harness/application.py`, `harness/observer.py` and transport adapters | Compose current ports/tools and bounded passive evidence views without granting observer authority. |
| `tools/` | Maintained setup/check/build/campaign entry points and generic Pi host. |
| `native/` | Upstream provenance and preparation inputs, not a semantic control backend. |
| `web/` | Passive spectator and independent user Pause. |
| `tests/` | Scoped behavioral assertions/doubles and compiled fixtures; actual outcomes are separate evidence. |
| `docs/components/`, `contracts/`, `standards/`, `workflows/`, `operations/` | Explanation, exact rules, mandatory qualities, decisions and supported tasks. |
| `docs/acceptance/`, `changes/`, `decisions/` | Dated evidence/rationale under explicit status, not live commands or permission. |
| Ignored `.runtime/` | Frozen inputs, owned stores/saves and raw evidence; no private maintained source framework. |

### Follow a concrete reader task

| Task | Current route and consequence |
| --- | --- |
| Send basic control | [Player guide](player-guide.md) → [tool schemas](../harness/player_tools.py) → [computer operations](contracts/computer-control.md#computer-operations-and-custody). No game-phase/identity admission. |
| Collect uncertain input | [Tool procedure](operations/mission-requests.md) → exact original `computer_result` / `player_result`. Input remains stopped; no replay. |
| Replace an actor | [Host procedure](operations/player-host.md) → [custody contract](contracts/computer-control.md#computer-operations-and-custody). Canonical context and actual quiescence precede successor capability. |
| Save/load/exit | [Player guide](player-guide.md#current-registered-cdda-lifecycle) → actual visible ordinary controls. The player judges game state; the harness certifies no save. |
| Investigate observed play | [Start/observe](operations/start-observe.md) → [observer component](components/observer-operations.md) → [passive projection contract](contracts/computer-control.md#passive-spectator-projections). Recorded inspection and current control target remain distinct. |
| Select validation | [Testing](testing.md) → [development policy](workflows/development.md) and [CI profiles](workflows/ci-profiles.md). Native/gameplay evidence stays separate. |

## One authoritative home per kind of fact

Charter owns purpose; engineering/standards own mandatory rules;
architecture/components own current responsibilities and assurance limits;
[computer-control](contracts/computer-control.md) owns exact current ports;
schemas/source own their declared executable interface; operations own tasks.
GitHub owns live work, proposals own unadopted scope, ADRs own dated rationale,
and acceptance reports own original observations. The control registry/map owns
control lifecycle, not a second contract or work tracker.

The [recorded investigation contract](contracts/observer-investigation.md) owns the
current bounded passive artifact. Other historical `contracts/` pages are superseded bookmarks for the native7/mission11
system. They retain original-source links and headings for historical references;
current readers follow their explicit replacement. Do not treat historical
contracts or old executable artifacts as another supported backend.

## Lifecycle and maintenance

Use `active`, `proposed`, `historical` or `superseded` stewardship metadata according
to artifact authority. Superseded guidance names a repository-relative replacement.
A timestamp or parser pass does not establish truth. Keep original failures intact.

Update parent/component/contract/callers/storage/operations together when behavior
changes. Incorporate adopted design into current pages, transfer remaining work
to GitHub and retain briefs as rationale. Preserve useful bookmarks while routing
them to the current rule. No extra backlog, registry or source-history database is
needed. C-USABILITY follows a real reader task; C-REVIEW compares claims with source;
C-MAINTENANCE checks drift at existing triggers. Valid paths/anchors/render receipts
support these judgments but cannot replace them.
