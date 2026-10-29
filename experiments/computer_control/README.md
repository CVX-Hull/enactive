# Isolated computer-control proof

This is #181's bounded development candidate, governed by
[the change brief](../../docs/changes/070-computer-control-proof.md) and
[ADR006](../../docs/decisions/006-computer-control-boundary.md). It is not the
product CLI or a second supported backend. All game meaning belongs to the player.

From the repository root, with the already prepared project-local SDL frameworks:

```sh
.venv/bin/python -m experiments.computer_control.build
.venv/bin/python -m unittest tests.test_computer_control tests.test_devtools
.venv/bin/python -m experiments.computer_control.native_check --output .runtime/NEW-fixture --via-shell
.venv/bin/python -m experiments.computer_control.native_check --output .runtime/NEW-loss-fixture --via-shell --offscreen --terminal target-loss
.venv/bin/python -m experiments.computer_control.native_lock_check --output .runtime/NEW-invalid-lock-fixtures
```

The native check launches an independent hidden SDL fixture, not CDDA or an LLM.
Its unit-scale resize and simulated takeover cannot qualify real-human input,
non-unit pointer transforms or another game. The build manifest retains the Git
checkpoint, dirty status, source/output hashes and actual compiler arguments.
The offscreen case keeps a smaller texture selected during input, while captures
remain full default output. Its renderer replacement must never regain custody.
Retain selected native/library bytes by hash before overwriting build outputs;
frozen manifests reference exact artifacts, not whatever a build cache later holds.

A real development run requires a fresh project-local directory containing the
frozen `computer-proof/2` manifest and its exact route, MCP, player context/prompt
and derived launch script. The custodian refuses dirty or different source and
changed files/binaries; it never reopens a started directory. It owns the exact
child and existing game lock.
Initial target configuration files are pinned in `initial_files` and checked before
launch; a source commit alone does not freeze application-owned configuration.
The owned native child retains the exact inherited
shared lock after its parent's copy closes, with close-on-exec set at library startup.
Old proof/1 launch profiles are rejected. Supply only the selected provider credential to
the custodian's environment, then invoke:

```sh
.venv/bin/python -m experiments.computer_control.run --run .runtime/NEW-proof
```

The four player tools expose actual pixels, basic input, original-result collection
and permanent stop. The passive localhost viewer can end dispatch independently.
Receipts describe delivery, never game success. Cancellation, takeover or uncertain
delivery cannot be repaired by replay/rearm. A new run needs a new frozen package
after the old actor and owned process are closed. Retain failures and normal-exit
versus forced-cleanup distinctions. No provider key reaches the game or MCP child.

The proof deliberately lacks the production mission ledger, programs/memory
succession and full spectator controls. #176 must integrate or retire every current
caller and remove this experiment as part of one supported contract. Historical
native7/mission11 evidence does not become authority for this candidate.
Actual CDDA clicking remains unqualified: delivery occurred without visible effect
under the inspected disabled-mouse configuration. Do not add a game-specific
override. Normal application input configuration and useful widget effects belong
to the next coordinated preparation/playing-system qualification.
