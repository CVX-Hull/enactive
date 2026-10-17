# CDDA Player

Read `docs/engineering.md`, `docs/architecture.md`, and the current work in
`docs/work.md` before changing boundaries. Global skills are optional reference
material, not this project's prescribed process. Do not import ceremony without
a concrete project need. User instructions take precedence.

- Keep new dependencies, game binaries, saves, caches, and build outputs under
  this project or its explicitly recorded temporary build directory. Never
  install global packages, change shell profiles, or modify other applications.
- Never launch fullscreen. Use the project user directory explicitly.
- Lead retains design, ownership briefs, adjudication, escalation, integration,
  and final verification. Explorers are read-only; workers own bounded named
  paths; reviewers read fresh context. Always name agent_type; workers and
  reviewers use fork_turns=none. One implementation writer at a time.
- Every brief identifies paths, decisions, and acceptance checks. Verify returned
  evidence. Take work back after two failed repair attempts or ownership drift.
- Preserve real CDDA behavior. No hidden state in normal observations, no save
  editing to win a demo, no bypassing engine validations.
- Tests and demo evidence are distinct. Never replace a real-game failure with
  a passing mock. Record failures and unknown outcomes honestly.
- Keep authoritative docs updated with behavior changes. No speculative APIs,
  unsolicited frameworks, or silent scope changes.
