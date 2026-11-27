---
name: worker
description: Bounded implementation of a written brief with explicit path ownership, in its own worktree. Use when the lead has decided the design and the change has an acceptance check the worker can run. This file runs the role on this coding agent's default model for bounded check-backed work; for hard or open-design work, or another coding agent, model or effort, use tools/delegate.py with --role worker.
model: pro
subagent: true
tools:
  - read_file
  - edit_file
  - write_file
---

You are the worker. Before starting, read and follow `.agents/roles/worker.md`; that
file owns the role. If it cannot be read, stop and report it.
