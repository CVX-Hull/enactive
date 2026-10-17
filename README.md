# CDDA Player

A project-local harness for playing real Cataclysm: Dark Days Ahead while a
person watches the graphical Tiles client and a spectator console.

**Status: implementation in progress. No gameplay demonstration has passed yet.**

- [Engineering practices](docs/engineering.md): standards and enforcement.
- [Architecture](docs/architecture.md): boundaries, control contract, decisions.
- [Research](docs/research.md): sources, confidence, and design consequences.
- [Work and acceptance](docs/work.md): current work and demonstrable outcomes.
- [Environment ledger](docs/environment.md): installations and cleanup.

The upstream game is GPL-licensed; it is a separately downloaded, pinned input.
The repository will contain a small auditable patch, not a vendored game tree.
No fullscreen launch, global package installation, or hidden-state gameplay.
