# Work and acceptance

Owner: lead. Updated: 2026-10-17. Goal remains active until real graphical
demonstration and required acceptance are complete.

| Slice | State | Exit evidence |
| --- | --- | --- |
| Research and environment comparison | Verified for initial decision | research.md; pinned source inspection; official graphical launch observed |
| Isolation and version control | Active | Git initialized; environment ledger records cleanup; first reviewed checkpoint pending |
| Contracts and maintained practices | Active | Engineering/architecture/research docs written; independent review and executable enforcement pending |
| Native input/observation bridge | Pending | Pinned game compiles, captures real frame, sends one action, rejects stale commands |
| Controller and spectator console | Pending | Serialized control, journal, responsive viewer, pause/takeover tests |
| Guarded skills and real demonstration | Pending | Scenarios below, continuous session, baseline comparison |
| Final review and handover | Pending | Checks, source review, docs match reality, clean global-environment audit |

## Acceptance matrix

No row is passed merely because implementation exists.

| Outcome | Required evidence | Result |
| --- | --- | --- |
| Reproducible local setup | Pinned source/assets, repeatable build/launch, no global installs | Pending |
| Attractive actual graphics | Windowed Tiles plus live viewer screenshot | Pending; stock graphics verified earlier, stock fullscreen corrected before further launch |
| Closed-loop actions | Movement observed before/after; menu and prompt transitions handled | Pending |
| Meaningful play | Leave shelter or explore, acquire/use an item through normal game rules | Pending |
| Interrupts | Pause, human takeover, stale command, context change, visible danger | Pending |
| Persistence | Normal save, stop, reload; no stale action replay | Pending |
| Efficiency | Same safe route, single-step versus guarded routine; count actions/calls/time | Pending |
| Honest failures | Distinguish transport unknown outcome from policy failure and engine result | Pending |
| Enforced practices | Common checks, local hook, review evidence, contract/doc updates | Pending |

## Immediate implementation brief

Lead owns the native integration because patch/build/real-input verification is
a tight iterative chain. A worker may subsequently own the Python service and
viewer against the reviewed bridge contract, one implementation writer at a
time. Native source inputs remain outside Git; track patch files and a setup
script that fails when the pinned source changes. Do not install global tools.

Next: independent contract review; implement the smallest frame/action vertical
slice; compile the actual game. Resolve compilation before expanding behavior.

## Maintenance triggers / deferred work

- Linux clean-room build: revisit for unattended/multiple sessions or if native
  isolation cannot meet requirements. No performance claims without measurement.
- Learned policies and large memory systems: defer until a baseline exposes a
  measured failure that they address.
- Remote spectator access / cloud service: outside local MVP; requires a new
  security and deployment design.
- Research refresh: at controller redesign or release after 90 days.

## Exceptions and incident record

Initial feasibility launch used CDDA's default directory and borderless mode;
the game was quit, fresh config moved project-local, and windowed options set.
Initial pkgconf global install was reversed. The unavoidable retained Homebrew
metadata refresh and exact cleanup are in environment.md. Future launch must
use explicit local userdir and windowed config.
