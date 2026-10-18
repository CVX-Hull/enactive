---
owner: maintainer
review_trigger: Deployment, trust boundaries or vulnerability reporting changes
status: active
---

# Security policy

Enactive is a local CDDA game-control harness. The spectator binds loopback and
browser controls validate origin and controller authority. These controls do not
make it a hosted service: public internet deployment, port forwarding and shared
remote access are unsupported. See the current
[architecture](docs/architecture.md#observation-and-deployment-boundaries) and
[protocol](docs/protocol.md) for the trust boundaries.

Keep controller tokens, bridge files, saves and local diagnostics private. Use the
prepared local setup and explicit project userdir. Do not expose the service or
its files through a public proxy or file share.

## Report a vulnerability privately

Use GitHub private vulnerability reporting:
[report a vulnerability](https://github.com/CVX-Hull/enactive/security/advisories/new).
This channel is enabled for this repository. If the private reporting option is unavailable, do not place exploit details or secrets
in public issues or pull requests.

Include the affected commit, environment, impact, minimal reproduction and any
suggested mitigation. Share only the information needed to investigate. Redact
tokens, credentials, personal paths and private gameplay data; do not attach saves
unless privately requested and you have checked their contents. Coordinate public
disclosure through the private report so a fix and its limits can be assessed.

Ordinary non-sensitive bugs belong in the bug issue form. There is no guaranteed
response or fix timeline, and no maintained release support matrix is promised.
