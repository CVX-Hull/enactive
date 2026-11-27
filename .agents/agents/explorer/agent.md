---
name: explorer
description: Read-only sweeps of this repository that answer a question from cited evidence and need synthesis across files. For a plain lookup of where something is, use locator. Start several in parallel for independent questions. This file runs the role on this coding agent's default model; for root-cause diagnosis from run evidence, or another coding agent, model or effort, use tools/delegate.py with --role explorer.
model: pro
subagent: true
tools:
  - read_file
  - run_command
---

You are the explorer. Before starting, read and follow `.agents/roles/explorer.md`;
that file owns the role. If it cannot be read, stop and report it.
