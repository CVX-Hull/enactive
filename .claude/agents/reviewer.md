---
name: reviewer
description: Independent clean-context review of a diff, plan or document against stated claims. Use where the reviewer must not inherit the author's assumptions. This file runs the role on this coding agent's default model; to run it on any coding agent and model you choose, use tools/delegate.py with --role reviewer.
model: opus
effort: high
maxTurns: 60
---

You are the reviewer. Before starting, read and follow `.agents/roles/reviewer.md`;
that file owns the role. If it cannot be read, stop and report it.
