# CDDA Player

A working local harness for **real Cataclysm: Dark Days Ahead**, with the native
Tiles game in a normal window and a browser spectator console. Codex is the
planner; the harness supplies observations, checked inputs, bounded movement,
and a visible action journal. No external model subscription or API key is
required. This is an MVP, not an unattended survival agent.

The 2026-10-17 demonstration created a survivor, used a flashlight, collected
supplies, drank water, explored the shelter and outdoors, saved/reloaded twice,
and cancelled native travel when a zombie appeared. The full results and known
limitations are in [work and acceptance](docs/work.md).

## Run

Follow [local setup](docs/setup.md) for a fresh checkout. On this prepared Mac,
run these in separate terminals from this directory:

```sh
.venv/bin/python -m harness serve --port 8766
.runtime/Cataclysm.app/Contents/MacOS/Cataclysm.sh
```

Open **http://127.0.0.1:8766/** to watch. Port 8766 avoids an existing unrelated
service on 8765. The current demonstration already has the game and service
running: do not start duplicates. The game is saved and remote control paused.

Use **Observe**, then **Resume**. A planner chooses an input from the frame and
passes its exact session/revision; copy the values returned by observe:

```sh
.venv/bin/python -m harness observe
.venv/bin/python -m harness resume
.venv/bin/python -m harness action inventory --expect SESSION:REVISION
.venv/bin/python -m harness walk north --steps 3 --expect SESSION:REVISION
.venv/bin/python -m harness pause
```

Resume changes revision, so use its returned value for the next decision. Every
input can change the revision or open a prompt. Read the result and actual frame
before deciding again; `ready` means the engine returned to input, not that an
objective succeeded. Advanced browser controls obey the same observation rule.
The goal field records an objective for Codex; it does not launch another agent.

**Pause control** stops further remote inputs. Native keyboard/button input also
latches remote pause. It cannot undo an input or cancel a game activity already
started: use the native game window to interrupt such activities. On timeout,
observe to reconcile and explicitly resume; never replay an uncertain action.
Use CDDA's normal Save menu before quitting the game. Stop the controller with
Ctrl-C; it leaves remote control paused. All saves stay in `.runtime/user/`.

## Evidence and maintenance

- [Engineering practices](docs/engineering.md): standards, enforcement, ownership.
- [Architecture](docs/architecture.md): authority, protocol, alternatives, recovery.
- [Research](docs/research.md): primary sources, recent agent/VLA evidence and limits.
- [Work and acceptance](docs/work.md): measured outcomes, failures, next priorities.
- [Environment ledger](docs/environment.md): installations and cleanup.
- [Setup and checks](docs/setup.md): pinned build and one common check command.
- [Third-party provenance](NOTICE.md): game, graphics, and bundled components.

Local demonstration artifacts are `.runtime/evidence/spectator-final.png`,
`zombie-interrupt.png`, and `gameplay-8x.mp4` (75.75 seconds, 8× playback of roughly
10 minutes of real renderer captures). They and the original journals are
ignored runtime evidence, not downloaded with a source checkout. The video ends
before the later zombie encounter; its separate screenshot and journal record
that event. No remote repository, publication, global hooks, or global package
installation is required.
