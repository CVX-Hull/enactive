---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# S-PROTOCOL Command and observation authority

Preserve the [protocol](../protocol.md): single writer, explicit session/revision,
unique identity, expiry, bounded inputs, observation provenance and no blind
retry of uncertain side effects. Game thread owns game state. Producer and
consumer versions must agree. A new version or native input change requires
real-game reconciliation/takeover probes; a mock cannot satisfy that lane.
Distinguish immutable capture provenance, original freshness/custody and the
preconditions of the chosen action. Require pixel equality where the decision is
image-conditioned; incidental rendering changes are not themselves a semantic
state change. Verify this boundary with real changed images, negative custody/
clock cases and a coherent lifecycle, not a screen mask or repeated retry loop.

Preserve the scope of a failure across input and observation entry points.
Healthy local game-time exhaustion returns partial work with original effects
and costs; it must not become a mission-wide ownership failure through a shared
exception base. Global budget, custody, clock and integrity failures still win.
Plain observation of an ordinary owned activity uses its own finite capture
allowance within the original mission/ending budget. An expired execution root
stays exhausted; it cannot grant input, renew itself or prevent healthy bounded
observation and explicit closure. Typed polls and inputs retain their root limits.
C-PORTABLE pairs local exhaustion with simultaneous global/fatal cases;
C-REVIEW checks that test expectations enforce the authoritative contract.

Distinguish transport collection ceilings, original execution/resource deadlines
and useful-response targets. Freeze supported transport configuration against the
actual operation envelope, including legitimate loading, before a new run; return
on an ACK rather than waiting out the ceiling. A longer ceiling neither proves the
cause of a missing ACK nor repairs lost correlation, and cannot relax routine
latency targets, renew authority or justify replay. C-REVIEW checks the frozen
configuration and actual receipts; C-NATIVE/C-USABILITY qualify the result.

[Standards index](../engineering.md).
