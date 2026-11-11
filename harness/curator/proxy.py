"""Model proxy for curator sessions (ADR 009 isolation; #451).

The proxy runs outside the sandbox on one loopback port. It holds the provider key; the curator
holds only a per-session token the proxy can revoke.

What reaches the provider is allowlisted, not filtered:
- **Route.** Only the provider's model route is forwarded.
- **Headers.** Only a few headers pass, and beta flags only from a frozen set. Responses
  are always requested uncompressed, so usage stays readable. For a provider with a
  session-affinity header the proxy sets one value per proxy, that is per session, on
  every request; the host's own value is never forwarded.
- **Body.** Top-level fields and content blocks are allowlisted. Inline text and base64
  images pass. Fetched or stored sources (URLs, files), documents, provider-run tools
  (server tools, MCP servers, containers), stored provider state and pricing tiers are
  refused.

Without that, a few-hundred-byte request could make the provider fetch any URL or bill far
above the reservation.

The dollar cap is enforced by reservation:
- **Reserve.** Before forwarding, the proxy reserves the worst case: every body byte counted
  as an input token at the highest input-side price, plus the requested output limit at the
  output price. A request whose reservation would exceed the cap is refused.
- **Settle.** Afterwards it settles at the reported usage. The response is read to the end
  even if the client has gone, so usage is not lost.
- **Fail closed.** A 200 response without usage keeps the whole reservation and revokes the
  session token. So does a charge above its reservation, recorded as a breach.

Every request is appended to the proxy's ledger, without the key or token. Prices are a frozen
input supplied by the caller (with their source and date), never a default.

This module holds no provider names. A `Provider` carries everything one provider needs (route,
key header, allowlists, extra request rules, forwarded headers, how usage turns into dollars);
the host adapter that talks to a provider defines it (`tools/curator_host/providers.py`) and
passes it in.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

MAX_BODY = 8 << 20
READ_TIMEOUT = 30
MAX_CONCURRENT = 8
# Headers every provider receives from the host; `Provider.forward_headers` adds its own.
FORWARD_HEADERS = frozenset({'content-type', 'accept', 'user-agent'})


@dataclass(frozen=True)
class Price:
    """US dollars per million tokens. `cache_write` must be the highest cache-write tier allowed."""
    input: Decimal
    output: Decimal
    cache_write: Decimal = Decimal(0)
    cache_read: Decimal = Decimal(0)

    @property
    def worst_input(self) -> Decimal:
        return max(self.input, self.cache_write, self.cache_read)


def no_refusal(_request: dict) -> str | None:
    return None


@dataclass(frozen=True)
class Provider:
    """How one provider authenticates, which request shapes are allowed and what a response costs.

    Everything provider-specific is data or a small callable here, so the proxy has no provider branch.
    """
    name: str
    routes: frozenset[str]
    key_header: str  # 'x-api-key' or 'authorization'
    output_field: str  # body field holding the output-token limit
    fields: frozenset[str]  # allowed top-level body fields
    blocks: frozenset[str]  # allowed content-block types
    tool_refusal: Callable[[dict], str | None]  # why one `tools` entry is refused, or None
    cost: Callable[[Price, dict[str, int], bytes], Decimal]  # (price, usage, raw response body) -> dollars
    request_refusal: Callable[[dict], str | None] = no_refusal  # extra body rules, run after the tool rule
    forward_headers: frozenset[str] = frozenset()  # lower-case headers forwarded besides FORWARD_HEADERS
    beta_header: str | None = None  # header listing beta flags; only flags in the proxy's frozen set pass
    affinity_header: str | None = None  # session-affinity header the proxy itself sets, if the provider has one

    def __post_init__(self):
        # The proxy sets these itself; a provider must not let the host's values through.
        owned = {'authorization', 'x-api-key', 'content-length', 'accept-encoding', 'transfer-encoding', 'host',
                 *(h.lower() for h in (self.key_header, self.beta_header, self.affinity_header) if h)}
        clash = sorted({h.lower() for h in self.forward_headers} & owned)
        if clash:
            raise ValueError(f'forward_headers may not carry headers the proxy sets: {", ".join(clash)}')

    def auth(self, key: str) -> tuple[str, str]:
        return (self.key_header, key) if self.key_header == 'x-api-key' else ('authorization', f'Bearer {key}')

    def presented(self, headers) -> str:
        value = headers.get('x-api-key') or ''
        bearer = headers.get('authorization') or ''
        return value or (bearer[7:] if bearer.lower().startswith('bearer ') else '')


def refusal(provider: Provider, request: object) -> str | None:
    """Why this request body may not be forwarded, or None."""
    if not isinstance(request, dict):
        return 'body must be a JSON object'
    extra = sorted(set(request) - provider.fields)
    if extra:
        return f'fields not allowed: {", ".join(extra)}'
    for tool in request.get('tools') or []:
        if not isinstance(tool, dict):
            return 'malformed tool'
        reason = provider.tool_refusal(tool)
        if reason:
            return reason
    reason = provider.request_refusal(request)
    if reason:
        return reason
    management = request.get('context_management')
    if management is not None:
        # Clearing old tool results or thinking only removes context; server-side compaction
        # runs extra model work whose billing is not verified, so it is refused.
        edits = management.get('edits') if isinstance(management, dict) else None
        if not isinstance(edits, list) or any(
                not isinstance(e, dict) or not str(e.get('type', '')).startswith(('clear_tool_uses_', 'clear_thinking_'))
                for e in edits):
            return 'only clearing context edits are allowed'
    # Walk every nested value of the conversation, except fields that are opaque arguments
    # or schemas rather than content.
    stack = [request.get('messages'), request.get('system'), request.get('input')]
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict):
            kind = item.get('type')
            if kind is not None and (not isinstance(kind, str) or kind not in provider.blocks):
                return f'content block {kind!r} not allowed'
            source = item.get('source')
            if isinstance(source, dict) and source.get('type') != 'base64':
                return 'only inline base64 sources are allowed'
            image_url = item.get('image_url')
            if isinstance(image_url, dict):  # chat completions: {"url": ..., "detail": ...}
                image_url = image_url.get('url')
            if 'image_url' in item and not (isinstance(image_url, str) and image_url.startswith('data:')):
                return 'only inline images are allowed'
            if 'file_id' in item or 'file_url' in item:
                return 'stored or fetched files are not allowed'
            stack.extend(v for k, v in item.items() if k not in OPAQUE)
    return None


# Each inline image reserves this many input tokens instead of its base64 bytes. Providers bill an
# image by its pixels, not its encoding, after scaling it to a bounded size (about 1,600 tokens at
# most for the providers in `tools/curator_host/providers.py`). 10,000 leaves several times that
# headroom. A charge above the reservation still revokes the session.
IMAGE_TOKENS = 10_000


IMAGE_MEDIA = re.compile(r'image/(png|jpeg|gif|webp)')
IMAGE_DATA_URL = re.compile(r'data:image/(png|jpeg|gif|webp);base64,')


def inline_images(request: object) -> tuple[int, int]:
    """The base64 bytes and count of inline images in an already-allowlisted request body.

    Only image content blocks count: an `image` block with a base64 `image/*` source,
    or an `image_url`/`input_image` part with a `data:image/...;base64,` URL. The walk skips the
    same opaque fields as `refusal`, so a tool argument or text that merely looks like an image
    is billed by its bytes.
    """
    total = count = 0
    stack = [request.get('messages'), request.get('system'), request.get('input')] if isinstance(request, dict) else []
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict):
            kind = item.get('type')
            data = None
            if kind == 'image':
                source = item.get('source')
                if (isinstance(source, dict) and source.get('type') == 'base64'
                        and isinstance(source.get('media_type'), str) and IMAGE_MEDIA.fullmatch(source['media_type'])):
                    data = source.get('data')
            elif kind in ('image_url', 'input_image'):
                url = item.get('image_url')
                url = url.get('url') if isinstance(url, dict) else url
                if isinstance(url, str) and IMAGE_DATA_URL.match(url):
                    data = url
            if isinstance(data, str):
                # The body is re-serialized compactly with ASCII escapes, so a base64 string's byte
                # length in the body equals its character length.
                total += len(data)
                count += 1
                continue
            stack.extend(v for k, v in item.items() if k not in OPAQUE)
    return total, count


# Fields whose values are tool arguments or schemas, not content blocks.
# `source` is checked where it appears; `cache_control` carries its own unrelated `type`.
OPAQUE = frozenset({'input', 'arguments', 'input_schema', 'parameters', 'data', 'text', 'thinking', 'signature',
                    'source', 'cache_control'})


def usage_of(body: bytes) -> dict[str, int] | None:
    """Token usage from a JSON or server-sent-event response, or None when absent.

    Integer counts are kept at their maximum across events; nested cache-creation detail is
    summed into `cache_creation_input_tokens` when the flat total is absent.
    """
    usage: dict[str, int] = {}
    for found in usage_events(body):
        for key, value in found.items():
            if isinstance(value, int) and not isinstance(value, bool):
                usage[key] = max(usage.get(key, 0), value)
        nested = found.get('cache_creation')
        if isinstance(nested, dict) and 'cache_creation_input_tokens' not in found:
            total = sum(v for v in nested.values() if isinstance(v, int) and not isinstance(v, bool))
            usage['cache_creation_input_tokens'] = max(usage.get('cache_creation_input_tokens', 0), total)
    return usage or None


def usage_events(body: bytes):
    """Every usage object in a JSON or server-sent-event response body."""
    text = body.decode('utf-8', 'replace')
    documents = [text] if text.lstrip().startswith('{') else [
        line[5:].strip() for line in text.splitlines() if line.startswith('data:')]
    for document in documents:
        try:
            event = json.loads(document, parse_float=Decimal)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        found = (event.get('usage') or (event.get('message') or {}).get('usage')
                 or (event.get('response') or {}).get('usage'))
        if isinstance(found, dict):
            yield found


class ModelProxy:
    """One proxy per session. `upstream` is the provider base URL (https in use; http only in tests)."""

    def __init__(self, *, provider: Provider, upstream: str, key: str, prices: dict[str, Price],
                 cap_usd: Decimal, ledger: Path, max_output_tokens: int = 64_000,
                 betas: frozenset[str] = frozenset(), routing: dict | None = None):
        parts = urlsplit(upstream)
        if parts.scheme not in ('https', 'http') or not parts.hostname or parts.path not in ('', '/'):
            raise ValueError('Upstream must be a bare http(s) origin')
        if not key or cap_usd <= 0 or not prices:
            raise ValueError('Proxy needs a key, a positive cap and frozen prices')
        self.provider, self.upstream, self._key = provider, parts, key
        self.prices, self.cap = dict(prices), Decimal(cap_usd)
        self.ledger, self.max_output_tokens, self.betas = ledger, max_output_tokens, frozenset(betas)
        # When set, every request must carry exactly this value in its `provider` field (which of the
        # provider's backends may serve it), so a host cannot widen it to fallbacks or other backends.
        self.routing = None if routing is None else json.loads(json.dumps(routing))
        self.token = secrets.token_hex(32)
        # One provider session-affinity value for this proxy, hence for the session, so the provider keeps the
        # session on one backend and its prompt cache. The proxy sets it; a value from the host is never
        # forwarded, and it is independent of the token. Only a short digest of it enters the ledger.
        self.affinity = 'curator-' + secrets.token_hex(16)
        self.affinity_digest = hashlib.sha256(self.affinity.encode()).hexdigest()[:16]
        self.spent = Decimal(0)
        self.reserved = Decimal(0)
        self.revoked = False
        self.breaches = 0
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(MAX_CONCURRENT)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # -- accounting -------------------------------------------------------
    def _reserve(self, model: str, body: bytes, output_limit: int, request: object = None) -> Decimal | str:
        price = self.prices.get(model)
        if price is None:
            return f'model {model!r} has no frozen price'
        if not (0 < output_limit <= self.max_output_tokens):
            return f'output limit must be between 1 and {self.max_output_tokens}'
        image_bytes, images = inline_images(request)
        input_tokens = len(body) - image_bytes + images * IMAGE_TOKENS
        worst = (input_tokens * price.worst_input + output_limit * price.output) / Decimal(1_000_000)
        with self._lock:
            if self.revoked:
                return 'session token revoked'
            if self.spent + self.reserved + worst > self.cap:
                return 'spend cap reached'
            self.reserved += worst
        return worst

    def _settle(self, reservation: Decimal, actual: Decimal | None, status: int) -> tuple[Decimal, bool]:
        """Charge the actual cost (or the reservation when unknown). Fail closed on surprises."""
        charge = reservation if actual is None else actual
        breach = actual is not None and actual > reservation
        with self._lock:
            self.reserved -= reservation
            self.spent += charge
            if breach or (actual is None and status == 200):
                self.revoked = True
            self.breaches += breach
        return charge, breach

    def _record(self, **entry):
        entry['time'] = time.time()
        with self._lock, self.ledger.open('a') as stream:
            stream.write(json.dumps(entry, default=str, sort_keys=True) + '\n')

    def revoke(self):
        with self._lock:
            self.revoked = True

    # -- serving ----------------------------------------------------------
    def start(self) -> int:
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            timeout = READ_TIMEOUT

            def log_message(self, *_args):
                pass

            def refuse(self, status: int, reason: str, **fields):
                proxy._record(path=urlsplit(self.path).path, status=status, refused=reason, **fields)
                data = json.dumps(dict(type='error', error=dict(type='curator_proxy', message=reason))).encode()
                self.send_response(status)
                self.send_header('content-type', 'application/json')
                self.send_header('content-length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self.refuse(404, 'route not allowed')

            def do_POST(self):
                if not proxy._slots.acquire(blocking=False):
                    self.close_connection = True
                    return self.refuse(429, 'too many concurrent requests')
                try:
                    self.handle_post()
                finally:
                    proxy._slots.release()

            def handle_post(self):
                path = urlsplit(self.path).path
                if not hmac.compare_digest(proxy.provider.presented(self.headers).encode(), proxy.token.encode()):
                    return self.refuse(401, 'unknown session token')
                if path not in proxy.provider.routes:
                    return self.refuse(404, 'route not allowed')
                if self.headers.get('transfer-encoding'):
                    return self.refuse(411, 'a content length is required')
                try:
                    length = int(self.headers.get('content-length', '-1'))
                except ValueError:
                    length = -1
                if not (0 <= length <= MAX_BODY):
                    return self.refuse(413, 'body length missing or too large')
                body = self.rfile.read(length)
                if len(body) != length:
                    return self.refuse(400, 'incomplete body')
                try:
                    request = json.loads(body)
                    reason = refusal(proxy.provider, request)
                    if reason is None and proxy.routing is not None and request.get('provider') != proxy.routing:
                        reason = 'provider routing must be the pinned routing'
                    body = json.dumps(request, separators=(',', ':')).encode()
                except (ValueError, TypeError, RecursionError):
                    return self.refuse(400, 'body must be well-formed JSON')
                if reason:
                    return self.refuse(400, reason)
                model = request.get('model')
                try:
                    output_limit = int(request.get(proxy.provider.output_field) or 0)
                except (TypeError, ValueError):
                    output_limit = 0
                listed = self.headers.get(proxy.provider.beta_header) if proxy.provider.beta_header else None
                betas = [b.strip() for b in (listed or '').split(',') if b.strip()]
                dropped = sorted(set(betas) - proxy.betas)
                reservation = proxy._reserve(model if isinstance(model, str) else '', body, output_limit, request)
                if isinstance(reservation, str):
                    return self.refuse(429, reservation, model=model)
                status, received, actual, error = 502, b'', None, None
                try:
                    status, received = self.forward(path, body, [b for b in betas if b in proxy.betas])
                except Exception as exc:  # noqa: BLE001 - every failure settles below and fails closed
                    error = type(exc).__name__
                finally:
                    usage = usage_of(received) if received else None
                    actual = None if usage is None else proxy.provider.cost(proxy.prices[model], usage, received)
                    charge, breach = proxy._settle(reservation, actual, status)
                    proxy._record(path=path, model=model, status=status, reserved=reservation, charged=charge,
                                  usage_missing=actual is None, breach=breach, error=error, dropped_betas=dropped,
                                  affinity_sha256=proxy.affinity_digest if proxy.provider.affinity_header else None)
                if error and not self.started:
                    self.refuse(502, f'upstream failed: {error}')
                elif self.started and self.client_open and not error:
                    try:
                        self.wfile.write(b'0\r\n\r\n')
                    except OSError:
                        pass
                elif self.started:
                    self.close_connection = True  # an unfinished chunked body: never reuse the connection

            started = False
            client_open = False

            def forward(self, path: str, body: bytes, betas: list[str]) -> tuple[int, bytes]:
                up = proxy.upstream
                connection_type = http.client.HTTPSConnection if up.scheme == 'https' else http.client.HTTPConnection
                connection = connection_type(up.hostname, up.port, timeout=600)
                passed = FORWARD_HEADERS | proxy.provider.forward_headers
                headers = {k: v for k, v in self.headers.items() if k.lower() in passed}
                if betas and proxy.provider.beta_header:
                    headers[proxy.provider.beta_header] = ','.join(betas)
                name, value = proxy.provider.auth(proxy._key)
                headers[name] = value
                if proxy.provider.affinity_header:
                    headers[proxy.provider.affinity_header] = proxy.affinity
                headers['accept-encoding'] = 'identity'
                headers['content-length'] = str(len(body))
                try:
                    connection.request('POST', path, body=body, headers=headers)
                    response = connection.getresponse()
                    encoding = (response.getheader('content-encoding') or 'identity').lower()
                    self.send_response(response.status)
                    self.started = True
                    for k, v in response.getheaders():
                        if k.lower() in ('content-type', 'request-id', 'retry-after', 'x-should-retry'):
                            self.send_header(k, v)
                    self.send_header('transfer-encoding', 'chunked')
                    self.end_headers()
                    received = bytearray()
                    client = True
                    while chunk := response.read1(65536):
                        received += chunk
                        if client:
                            try:
                                self.wfile.write(b'%x\r\n%s\r\n' % (len(chunk), chunk))
                                self.wfile.flush()
                            except OSError:
                                client = False  # keep reading so the usage is settled
                    # The final chunk is written by the caller after settlement, so a client
                    # never sees a complete response before its charge and any revocation.
                    self.client_open = client
                    # An encoded body cannot be read for usage: settle it as missing usage.
                    return response.status, bytes(received) if encoding == 'identity' else b''
                finally:
                    connection.close()

        self._server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self._server.server_port

    def close(self):
        self.revoke()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(5)
