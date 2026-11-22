---
owner: lead
status: historical
date: '2026-11-22'
scope: 'Design for the coverage-gated context cut implemented in #900 under player-host/10'
replacement: docs/contracts/player-host.md
---

# A context cut bounded by published coverage

## At a glance

- **Question.** Can the host release old turns while preserving enough context for the player's current task?
- **Proposal.** Remove only a prefix covered by a published snapshot and deliver a fresh briefing in the same request.
- **Unknown.** Lag in real play was measured in `#889` (17/17 live windows kept pace); whether the briefing preserves all needed distinctions across real cuts in live play remains to be observed after implementation.
- **Decision.** On 22 November 2026 the owner chose **Go** to implement the cut under [#900](https://github.com/CVX-Hull/enactive/issues/900) ([owner decision](../decisions/owner-decisions-archive.md#context-cut-go-and-archive-889), [decision brief](../acceptance/2026-11-22-context-cut-decision-brief-890.md)).

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
drops in the back-to-back simulation. Curator lag beside play was measured in
[#889](../acceptance/2026-11-22-live-validation-run-889.md) (17 of 17 live windows kept
pace); the player's ability to continue its task after a real cut still needs
measurement in live play.
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
