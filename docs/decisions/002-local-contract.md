# ADR 002 — Local serialized bridge and small service

Owner: maintainer. Status: accepted; reconstructed from the implemented MVP on
2026-10-17. Review on transport, distribution, dependency or concurrency change.

## Context and decision

One local game needs bounded commands at real input boundaries, visible results,
and predictable takeover. The game's thread retains all game-state access.
Use a private atomic-file bridge with one controller, a loopback Python service,
and a browser viewer of actual rendered frames. Current Python uses its standard
library; the viewer uses browser modules; the native patch follows upstream C++.
These stack choices are revisable decisions supporting P-CHANGE and P-ISOLATION.

## Alternatives and consequences

An embedded network API could provide streaming and richer contracts but adds
native service lifecycle and concurrency responsibilities. Screen-only input
avoids a source patch but weakens context and outcome recognition. A larger
application framework could help packaging or validation, but introduces its
own dependencies and upgrade work. These alternatives have not been benchmarked.

Files keep the native integration narrow but require explicit claims, expiry,
atomic publication, retirement, and ambiguity handling. The host's process lock
is not an OS security sandbox. Browser input requires origin/token checks.
A local Python standard-library service is not a deployment choice for public
internet exposure. Current guarantees are in [protocol](../protocol.md).

## Revisit conditions

Re-evaluate when multiple consumers, remote access, packaging, typed contracts,
streaming throughput or maintenance measurements justify a different transport
or framework. A dependency may be preferable when it supplies a concrete, tested
capability at lower total maintenance cost. Pin it locally, record provenance,
inspect licenses, and verify the migration. No general plugin system is required.
