---
owner: lead
status: active
review_trigger: A control fails, is bypassed or costs more than expected, or its boundary changes
---

# Controls

Each control below stops a named failure. A standard in [engineering](engineering.md)
names the controls it relies on; this page owns what each control stops, where it is
enforced and what it does not cover. A control is reviewed when it fails, is
bypassed, costs more than expected, or its boundary changes; the issue that changes it
records the finding ([ADR 010](decisions/010-streamlined-delivery.md)). Automatic
controls run in `tools/check.py`; runtime controls act in the live system and their
tests cover the stated cases only; manual controls are the named review or probe.

| Control | Mode | Failure it stops | Enforced by | Known gap |
| --- | --- | --- | --- | --- |
| C-PORTABLE | automatic | A change breaks portable behaviour (computer, player, adapters, records, viewer) without anyone noticing | The required `controller` check on every pull request ([CI profiles](workflows/ci-profiles.md)); local `--fast` and the opt-in pre-commit hook | Reduced profiles are not full passes; a push to main reruns no tests and relies on main's ruleset. Fixtures do not run the game, qualify a model or prove useful cadence |
| C-RUNTIME | runtime | An actor or observer gains input authority it must not have, or uncertain input is replayed | `harness/server.py`, the computer runtime and custody, the spectator's Pause; regressions in C-PORTABLE | Fixtures establish their stated boundaries only; unknown original delivery stays unknown; a game that stops polling past the continuation bound still fences input |
| C-NATIVE | manual | A native, input, rendering, protocol or source-pin change ships without real-game evidence | [Native acceptance](operations/native-acceptance.md) and the live permission preflight before campaign input | Bounded macOS SDL evidence on recorded sources; no other host, Unicode/IME or actual-human takeover is qualified |
| C-USABILITY | manual | The operator cannot tell what is running, what it controls or what to do next | Review of the overview, navigation and spectator under S-UX | Human judgment only; no usability score; whole-player responsiveness remains unqualified |
| C-BOUNDARY | automatic | Code crosses an architectural boundary (computer, player, adapters, evaluation, viewer, curator) or current text names a specific host | Import Linter's contracts in `pyproject.toml`, with negative fixtures in `tests/test_devtools.py` for the computer, player, adapter, evaluation, viewer and server contracts; the host-neutrality scan (`tests/test_host_neutrality.py`) | Static imports only; dynamic imports and generic descriptions of host-specific behaviour need review; the trace and curator contracts have no negative fixture |
| C-REVIEW | manual | A consequential design or change merges without the scrutiny its risk needs | [Review by decision and risk](workflows/review.md); independent clean-context review for boundary and outcome changes | Same-account agent review is not human approval; review quality is judgment |
| C-DOCUMENTS | automatic | Documents carry broken links or metadata, stale record indexes, unknown schema ids, malformed acceptance manifests, or tracked run data that disagrees with its pages | `tools/documents.py`, `tools/check.py`'s link check, `tools/run_ledger.py`, the generated run tables | Structure and references only, not prose truth; historical-origin fragments and external links are not checked |
| C-SETUP | runtime | Setup writes outside the project, uses unpinned inputs or skips a stage | `tools/setup.py`, `tools/build_computer.py`, `tools/prepare_game.py` stage guards; setup regressions | Real downloads and native builds are validated on this Mac only |
| C-RELEASE | manual | An unreviewed or untested candidate reaches main | Main's ruleset 25346774: pull requests only, the required `controller` check from the Actions app, strict up-to-date status, squash only, no bypass actors | Zero required human approvals (single account); rules can be changed by an administrator; no release automation |
| C-MAINTENANCE | manual review, automatic evidence check | Guidance, dependencies or evidence drift; cited evidence is lost | Event-triggered review; `tools.evidence verify` in every check: a missing, extra or writable sealed file, a changed total size, or a missing store on a clone that held it fails, and the full profile also compares every hash | The store is the only copy: its loss is detected, not undone; CI has no store, so only local runs verify it; evidence outside the store is unchecked until sealed |
| C-VISUAL | automatic | A diagram does not render or lacks a title and description | `tools/diagrams.py` render and receipt check | Rendering does not prove meaning or readable layout |
