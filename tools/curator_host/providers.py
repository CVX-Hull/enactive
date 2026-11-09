"""The model providers a curator host can reach, as values for `harness.curator.proxy.ModelProxy`.

The proxy is provider-neutral; each `Provider` here carries what is specific to one provider: its
route, key header, request allowlists, extra refusals, forwarded headers and how a response's
usage becomes dollars. Provider and model names belong in the host adapters (S-ARCH, ADR 010).

Image reservation (`harness.curator.proxy.IMAGE_TOKENS`): a provider bills an image by its pixels
after scaling, not by its encoding. Anthropic bills about width x height / 750 tokens after scaling
to at most about 1.15 megapixels (about 1,600 tokens).
"""
from __future__ import annotations

from decimal import Decimal

from harness.curator.proxy import Price, Provider, usage_events

PER = Decimal(1_000_000)

# Headers the proxy has always passed for every provider: the API version and the beta flags (the
# latter only from the proxy's frozen set).
COMMON = dict(forward_headers=frozenset({'anthropic-version'}), beta_header='anthropic-beta')


# -- Anthropic messages ------------------------------------------------------------------------
def _anthropic_tool(tool: dict) -> str | None:
    if 'input_schema' not in tool or tool.get('type') not in (None, 'custom'):
        return 'only client tools with an input schema are allowed'
    return None


def _anthropic_request(request: dict) -> str | None:
    management = request.get('context_management')
    if management is not None:
        # Clearing old tool results or thinking only removes context; server-side compaction
        # runs extra model work whose billing is not verified, so it is refused.
        edits = management.get('edits') if isinstance(management, dict) else None
        if not isinstance(edits, list) or any(
                not isinstance(e, dict) or not str(e.get('type', '')).startswith(('clear_tool_uses_', 'clear_thinking_'))
                for e in edits):
            return 'only clearing context edits are allowed'
    return None


def _anthropic_cost(price: Price, usage: dict[str, int], _body: bytes) -> Decimal:
    return (usage.get('input_tokens', 0) * price.input + usage.get('output_tokens', 0) * price.output
            + usage.get('cache_creation_input_tokens', 0) * price.cache_write
            + usage.get('cache_read_input_tokens', 0) * price.cache_read) / PER


ANTHROPIC = Provider(
    'anthropic', frozenset({'/v1/messages'}), 'x-api-key', 'max_tokens',
    frozenset({'model', 'max_tokens', 'messages', 'system', 'tools', 'tool_choice', 'stream', 'metadata',
               'stop_sequences', 'thinking', 'output_config', 'cache_control', 'temperature', 'top_p', 'top_k',
               'context_management'}),
    frozenset({'text', 'image', 'tool_use', 'tool_result', 'thinking', 'redacted_thinking'}),
    tool_refusal=_anthropic_tool, cost=_anthropic_cost, request_refusal=_anthropic_request, **COMMON)


# -- OpenRouter chat completions ---------------------------------------------------------------
# (#454; ADR 009 open decision 2). Checked on 8 November 2026 against
# openrouter.ai/docs/api/reference/overview, /docs/use-cases/usage-accounting and /docs/faq:
# - usage, including `cost`, is always returned, and the base currency is US dollars;
# - `plugins` (`web` is live web search), `models` and `route` (fallback models), `prompt`, `debug`
#   and `user` are left out of the allowlist;
# - `image_url` accepts remote URLs, so only `data:` URLs pass.
# The fields are those the project's curator host serializer sends for an OpenRouter model.

# Provider preferences that only choose among backends for the requested model.
ROUTING = frozenset({'order', 'only', 'ignore', 'allow_fallbacks', 'require_parameters', 'data_collection', 'zdr'})


def _openrouter_tool(tool: dict) -> str | None:
    return None if tool.get('type') == 'function' else 'only function tools are allowed'


def _openrouter_request(request: dict) -> str | None:
    routing = request.get('provider')
    if routing is not None and not (isinstance(routing, dict) and set(routing) <= ROUTING):
        return 'provider routing may only order, require or restrict providers'
    if request.get('store') not in (None, False):
        return 'provider-side storage is not allowed'
    return None


def _amount(value) -> Decimal | None:
    if isinstance(value, (Decimal, int)) and not isinstance(value, bool) and value >= 0:
        return Decimal(value)
    return None


def reported_cost(body: bytes) -> Decimal | None:
    """The whole charge for a request (US dollars), or None when the provider reported none.

    OpenRouter's `usage.cost` is what it bills the account. On a bring-your-own-key route that is
    only its fee: the provider bills `cost_details.upstream_inference_cost` to the operator's own
    key. Both are counted, so the cap tracks the real spend on either route.
    """
    charges = []
    for found in usage_events(body):
        cost = _amount(found.get('cost'))
        details = found.get('cost_details') if isinstance(found.get('cost_details'), dict) else {}
        upstream = _amount(details.get('upstream_inference_cost'))
        if cost is None and upstream is None:
            continue
        charges.append((cost or Decimal(0)) + (upstream or Decimal(0)) if found.get('is_byok') is True
                       else max(cost or Decimal(0), upstream or Decimal(0)))
    return max(charges) if charges else None


def _openrouter_cost(price: Price, usage: dict[str, int], body: bytes) -> Decimal:
    # The provider's reported charge is authoritative. Without it, all prompt tokens are
    # charged at the highest input-side price, so cache writes are never undercounted.
    reported = reported_cost(body)
    if reported is not None:
        return reported
    return (usage.get('prompt_tokens', 0) * price.worst_input + usage.get('completion_tokens', 0) * price.output) / PER


OPENROUTER = Provider(
    'openrouter', frozenset({'/api/v1/chat/completions'}), 'authorization', 'max_completion_tokens',
    frozenset({'model', 'messages', 'stream', 'stream_options', 'max_completion_tokens', 'temperature', 'top_p',
               'tools', 'tool_choice', 'reasoning', 'provider', 'store'}),
    frozenset({'text', 'image_url', 'function', 'reasoning.text', 'reasoning.summary', 'reasoning.encrypted'}),
    tool_refusal=_openrouter_tool, cost=_openrouter_cost, request_refusal=_openrouter_request,
    affinity_header='x-session-id', **COMMON)
