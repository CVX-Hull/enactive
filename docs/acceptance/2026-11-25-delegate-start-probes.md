---
owner: lead
status: historical
kind: measurement
date: '2026-11-25'
scope: 'Probes of the delegate starts on Codex CLI 0.171.0, Claude Code 2.1.329 and Antigravity CLI 1.5.17 for issues #975 and #978: what each coding agent reports about token use and the served model, whether a reviewer start can read a retained game frame, and how a quota refusal arrives; subscription quota only, no game launch, no game input'
---

# Delegate start probes: usage output, frame reading and a quota refusal

## At a glance

All three coding agents report token counts in machine-readable output, and only
Claude Code reports the model it served. A Claude Code start that named the alias
`haiku` reported Claude Sonnet 5.5. Four reviewer starts opened two retained game
frames and answered eight questions of fact about them, 32 of 32 correct. An
Antigravity start on a model whose quota was spent was reported by the delegate call as
`refused`, and the same refusal then met a second Gemini model.

The runs' output files are retained as
[`delegate-start-probes`](../../data/evidence/delegate-start-probes.sha256); the paths
below are inside it. The [attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl)
rows for issues 975 and 978 carry the delegate-call runs.

## Usage output

Each coding agent was started once by hand with a one-word prompt and its
machine-readable output flag (`usage-output/by-hand/`), and then once through
`tools/delegate.py` as a locator on its smallest model
(`usage-output/through-the-call/`). The table's fields are read from those outputs.

| | Codex CLI 0.171.0 | Claude Code 2.1.329 | Antigravity CLI 1.5.17 |
| --- | --- | --- | --- |
| Flag | `--json` | `--output-format json` | `--output-format json` |
| Output | One JSON record a line; `turn.completed` carries the counts | One JSON object | One JSON object |
| Input tokens | `usage.input_tokens`, cached tokens included | `usage.input_tokens`, cached tokens left out | `usage.input_tokens`; whether it includes cached tokens is undetermined: the locator run reported 16,122 input with 11,681 cached, and the Gemini 4 Carbon frame run 21,821 input with 25,579 cached |
| Cached input | `usage.cached_input_tokens` | `usage.cache_read_input_tokens` | `usage.cache_read_tokens` |
| Cache writes | `usage.cache_write_input_tokens` | `usage.cache_creation_input_tokens` | not reported |
| Output tokens | `usage.output_tokens` | `usage.output_tokens` | `usage.output_tokens` |
| Served model | not reported | the keys of `modelUsage` | not reported |
| Turns in one run | one `turn.completed` in the locator run | one object at the end | one object at the end |

None reports the share of a subscription window a run used.

## The Claude alias `haiku`

| Model named | Model reported in `modelUsage` | Runs |
| --- | --- | --- |
| `haiku` | `claude-sonnet-5-5` | Two: `usage-output/by-hand/claude.out` and `usage-output/through-the-call/claude-alias/result.json` |
| `claude-haiku-5-5` | `claude-haiku-5-5` | One: `usage-output/through-the-call/claude-id/result.json` |

The cause is not established.

## Frame reading

Each start was given the reviewer role, a directory holding only the role file, the
glossary and two frames under neutral names, and eight questions whose answers the lead
fixed from the frames beforehand (`frame-reading/brief.txt` holds the questions, and
each start's directory its result and reply). The frames are
`docs/acceptance/assets/correction-014/inventory.png` and
`docs/acceptance/assets/diagnosis-314/a1-stealing-prompt.png`. The questions ask for
text on an inventory screen (an item, a battery reading, two counts) and on a prompt
screen (the highlighted button, the date and time, a name, four attribute values).

| Start | Opened both frames with | Correct | Wall time |
| --- | --- | --- | --- |
| Claude Code, Claude Opus 5.5 at High | its file-reading tool | 8 of 8 | 19 s |
| Codex, GPT-6.2 Sol at Extra-high | `view_image` | 8 of 8 | 16 s |
| Codex, GPT-6.2 Astra at Medium | `view_image` | 8 of 8 | 16 s |
| Antigravity, Gemini 4 Carbon at High | its file-reading tool | 8 of 8 | 152 s |
| Antigravity, Gemini 4 Neon at High | refused on quota; no answers | none | 2 s |

A clean-context reviewer on Codex GPT-6.2 Astra at Medium compared the four replies
with the key and confirmed the 32 answers.

## The quota refusal

The Gemini 4 Neon start ended with a non-zero exit, an empty reply and the line
"Individual quota reached. Please upgrade your subscription to increase your limits.
Resets in 117h19m51s." The delegate call reported `refused` with that line as its
detail (`frame-reading/neon-high/`). Gemini 4 Carbon completed its frame run after
that. In a later review run it was refused 44 seconds in, and again at the start of the
next, with the same wording and three minutes less left until the reset (`quota-refusal/`).
The limit that refused Neon therefore also covers Carbon; how the two models draw on it
is not established.

## Limits

- Each statement rests on the runs its section names: one or two for each usage field
  and for the alias, five starts for frame reading of which four answered, three
  refusals. No repeat on another day or version.
- The frame questions read text and one highlight. Comparing two frames, reading a map
  and judging a tile scene were not asked.
- The starts' working directory held the frames under neutral names and none of the
  repository's text, and no start was told the frames' origin. Nothing confined a start
  to that directory or kept it off the network.
- No quota refusal was seen on Codex or Claude Code.
