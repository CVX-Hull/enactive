---
owner: maintainer
review_trigger: Product scope, entry points or setup changes
status: active
---

# CDDA Player

A local harness for real **Cataclysm: Dark Days Ahead** with a normal graphical
game window and browser spectator console. Codex chooses goals and interprets
screens; the harness supplies checked inputs, observations and bounded movement.
An active chat is required for planning. General autonomous survival is not implemented.

**Start with the [project overview](docs/overview.md)** for what works, limitations,
the system picture, current direction and decisions. It links to progressively
deeper design and evidence so you can review the big picture without reading code.

## Use and contribute

- [Set up locally](docs/setup.md): pinned inputs, isolated build and common checks.
- [Run, pause and recover](docs/runbook.md): commands, takeover, uncertainty and cleanup.
- [Current work](docs/work.md): next outcomes, blockers, exceptions and deferred work.
- [Public Project](https://github.com/users/CVX-Hull/projects/2) and
  [Issues](https://github.com/CVX-Hull/cdda-player/issues): authoritative work status.
- [Contributing](CONTRIBUTING.md) and [project workflow](docs/project-management.md).
- [Charter](docs/charter.md): purpose, constraints, principles and quality priorities.
- [Architecture](docs/architecture.md): current responsibilities and authority.
- [Engineering standards](docs/engineering.md) and [control map](docs/controls.md).
- [Research](docs/research.md), [environment history](docs/environment.md),
  [third-party provenance](NOTICE.md).

The [2026-10-17 demonstration](docs/acceptance/2026-10-17-mvp.md) covered supplies,
item use, exploration, save/reload and a visible-zombie interruption. Dated evidence
is not live process status or a guarantee of every game state. Pause prevents
further remote dispatch; an existing native activity may need native interruption.

Git contains small [acceptance provenance](docs/acceptance/2026-10-17-mvp-manifest.json).
Large screenshots, video and journals remain local under ignored `.runtime/` and
are unavailable in a fresh source checkout. The public repository contains source
and small review artifacts; no global package installation or scheduled background
agent is needed. Original work is [MIT licensed](LICENSE); CDDA-derived code and
third-party assets retain the terms in [NOTICE](NOTICE.md).
