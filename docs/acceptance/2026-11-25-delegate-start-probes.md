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
`refused`, and the same refusal then met two other Gemini models.

Each probe is one or two runs. The result files stayed in the lead's scratch space and
are not retained; the [attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl)
rows for issues 975 and 978 carry the runs' outcomes, times and token counts.

## Usage output

Each coding agent was started once by hand with a one-word prompt and its
machine-readable output flag, and then once through `tools/delegate.py` as a locator on
its smallest model.

| | Codex CLI 0.171.0 | Claude Code 2.1.329 | Antigravity CLI 1.5.17 |
| --- | --- | --- | --- |
| Flag | `--json` | `--output-format json` | `--output-format json` |
| Output | One JSON record a line; `turn.completed` carries the counts | One JSON object | One JSON object |
| Input tokens | `usage.input_tokens`, cached tokens included | `usage.input_tokens`, cached tokens left out | `usage.input_tokens`; the locator run reported 16,122 with 11,681 cached, so cached tokens appear to be included |
| Cached input | `usage.cached_input_tokens` | `usage.cache_read_input_tokens` | `usage.cache_read_tokens` |
| Cache writes | `usage.cache_write_input_tokens` | `usage.cache_creation_input_tokens` | not reported |
| Output tokens | `usage.output_tokens` | `usage.output_tokens` | `usage.output_tokens` |
| Served model | not reported | the keys of `modelUsage` | not reported |
| Turns in one run | one `turn.completed` in the locator run | one object at the end | one object at the end |

None reports the share of a subscription window a run used.

## The Claude alias `haiku`

| Model named | Model reported in `modelUsage` | Runs |
| --- | --- | --- |
| `haiku` | `claude-sonnet-5-5` | Three: two by hand, one through the delegate call |
| `claude-haiku-5-5` | `claude-haiku-5-5` | Two: one by hand, one through the delegate call |
| `opus` | `claude-opus-5-5` | One by hand |

One of the hand runs unset `CLAUDE_CODE_SUBAGENT_MODEL`; the user's settings file sets
it to `sonnet`, and a start loads that file, so that run does not show whether the
setting is the cause. The cause is not established.

## Frame reading

Each start was given the reviewer role, a directory holding only the role file, the
glossary and two frames under neutral names, and eight questions whose answers the lead
fixed from the frames beforehand. The frames are
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
detail. A Gemini 4 Carbon start 44 seconds into a later run, and a Gemini 4 Hydrogen
start by hand, were refused with the same wording and the same reset time, so the limit
that was reached is the account's and not one model's.

## Limits

- One or two runs for each statement; no repeat on another day or version.
- The frame questions read text and one highlight. Comparing two frames, reading a map
  and judging a tile scene were not asked.
- The frames were copied out of the checkout, so no start could read the answers from
  the repository's text; a start with network access could in principle have reached
  the public repository, and none was told the frames' origin.
- No quota refusal was seen on Codex or Claude Code.
