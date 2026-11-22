---
owner: lead
status: proposed
review_trigger: Measurement of the curator's confirmed coverage lag behind the player during real play
---

# A context cut bounded by published coverage

## At a glance

- **Question.** Can the host release old turns while preserving enough context for the player's current task?
- **Proposal.** Remove only a prefix covered by a published snapshot and deliver a fresh briefing in the same request.
- **Unknown.** Lag in real play determines how many turns can be released. Whether the briefing preserves the needed distinctions is unmeasured.
- **Decision.** The owner revisits adoption after [curator lag behind play is measured](../decisions/owner-decisions.md#context-cut-waits-for-curator-lag-measurement).

The alternatives considered and the lag estimates are in the
[retired context design](player-context.md).

## The cut

A request is one model call. A turn pairs a tool call with its result. The window
is the set of turns still in the prompt.

At the high token mark or the route's image peak, whichever comes first, the host
would remove old turns with their images toward the low token mark. Both token marks
count above the briefing's size. A cut would free at least ten turns. One marker
would identify the removed decisions and direct the player to their frames through
`player_source`. The most recent turns would stay verbatim.

The free checks use 20,000 and 60,000 tokens for the low and high marks. At about
950 tokens per turn and a peak of 39 images, the first trigger falls near 40,000
tokens. These are simulation parameters. Sessions of 15 decisions avoided image-block
drops in the back-to-back simulation. The lag beside play and the player's ability
to continue its task after a cut still need measurement.
[Cut simulation](../acceptance/2026-11-13-memory-screen-free-checks.md#where-the-cut-stops-working)

## Publication conditions

The publication would identify the decisions its confirmed prefix covers. When
it trails play, the host would shorten or defer the cut, continuing with ordinary
image eviction and capacity handoff. Play would never wait for publication.
The proposal would use the latest available publication at handoff without delaying
the successor. A later publication already reaches a running actor as an appended
difference that preserves the prefix already sent
([a newer version during play](../contracts/player-host.md#a-newer-version-during-play));
the cut would not change that path.
The [runner](../components/curator.md#publication-and-coverage) supplies the coverage
evidence. The [host contract](../contracts/player-host.md#delivered-knowledge-and-recall)
defines the export available to actors today.
