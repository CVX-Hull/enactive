"""Model proxy for curator sessions (ADR 009 isolation; #451).

The proxy runs outside the sandbox on one loopback port. It holds the provider key; the curator
holds only a per-session token the proxy can revoke. It forwards only allowlisted model routes
and enforces a dollar cap by reservation: before forwarding, it reserves the request's
worst-case cost (every body byte counted as an input token at the highest input-side price, plus
the requested output limit at the output price) and refuses a request whose reservation would
exceed the cap. Afterwards it settles at the reported usage, or keeps the whole reservation when
usage is missing. Every request is appended to the proxy's ledger.

Prices are a frozen input supplied by the caller (with their source and date), never a default.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit

HOP_HEADERS = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers',
               'transfer-encoding', 'upgrade', 'host', 'content-length', 'x-api-key', 'authorization'}
MAX_BODY = 32 << 20


@dataclass(frozen=True)
class Price:
    """US dollars per million tokens."""
    input: Decimal
    output: Decimal
    cache_write: Decimal = Decimal(0)
    cache_read: Decimal = Decimal(0)

    @property
    def worst_input(self) -> Decimal:
        return max(self.input, self.cache_write, self.cache_read)


@dataclass(frozen=True)
class Provider:
    """How one provider authenticates and reports usage."""
    name: str
    routes: frozenset[str]
    key_header: str  # 'x-api-key' or 'authorization'
    output_field: str  # body field holding the output-token limit

    def auth(self, key: str) -> tuple[str, str]:
        return (self.key_header, key) if self.key_header == 'x-api-key' else ('authorization', f'Bearer {key}')

    def presented(self, headers) -> str:
        value = headers.get('x-api-key') or ''
        bearer = headers.get('authorization') or ''
        return value or (bearer[7:] if bearer.lower().startswith('bearer ') else '')


ANTHROPIC = Provider('anthropic', frozenset({'/v1/messages'}), 'x-api-key', 'max_tokens')
OPENAI = Provider('openai', frozenset({'/v1/responses'}), 'authorization', 'max_output_tokens')


def usage_of(provider: Provider, body: bytes) -> dict[str, int] | None:
    """Token usage from a JSON or server-sent-event response, or None when absent."""
    text = body.decode('utf-8', 'replace')
    documents = []
    if text.lstrip().startswith('{'):
        documents.append(text)
    else:
        documents += [line[5:].strip() for line in text.splitlines() if line.startswith('data:')]
    usage: dict[str, int] = {}
    for document in documents:
        try:
            event = json.loads(document)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        found = (event.get('usage') or (event.get('message') or {}).get('usage')
                 or (event.get('response') or {}).get('usage'))
        if isinstance(found, dict):
            for key, value in found.items():
                if isinstance(value, int) and not isinstance(value, bool):
                    usage[key] = max(usage.get(key, 0), value)
    return usage or None


def cost_of(provider: Provider, price: Price, usage: dict[str, int]) -> Decimal:
    per = Decimal(1_000_000)
    if provider is ANTHROPIC:
        return (usage.get('input_tokens', 0) * price.input + usage.get('output_tokens', 0) * price.output
                + usage.get('cache_creation_input_tokens', 0) * price.cache_write
                + usage.get('cache_read_input_tokens', 0) * price.cache_read) / per
    # Cached input is charged at the full input price: conservative until a dated provider source
    # for cached-token pricing is frozen with the prices.
    return (usage.get('input_tokens', 0) * price.input + usage.get('output_tokens', 0) * price.output) / per


class ModelProxy:
    """One proxy per session. `upstream` is the provider base URL (https in use; http only in tests)."""

    def __init__(self, *, provider: Provider, upstream: str, key: str, prices: dict[str, Price],
                 cap_usd: Decimal, ledger: Path, max_output_tokens: int = 64_000):
        parts = urlsplit(upstream)
        if parts.scheme not in ('https', 'http') or not parts.hostname or parts.path not in ('', '/'):
            raise ValueError('Upstream must be a bare http(s) origin')
        if not key or cap_usd <= 0 or not prices:
            raise ValueError('Proxy needs a key, a positive cap and frozen prices')
        self.provider, self.upstream, self._key = provider, parts, key
        self.prices, self.cap = dict(prices), Decimal(cap_usd)
        self.ledger, self.max_output_tokens = ledger, max_output_tokens
        self.token = secrets.token_hex(32)
        self.spent = Decimal(0)
        self.reserved = Decimal(0)
        self.revoked = False
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # -- accounting -------------------------------------------------------
    def _reserve(self, model: str, body: bytes, output_limit: int) -> Decimal | str:
        price = self.prices.get(model)
        if price is None:
            return f'model {model!r} has no frozen price'
        if not (0 < output_limit <= self.max_output_tokens):
            return f'output limit must be between 1 and {self.max_output_tokens}'
        worst = (len(body) * price.worst_input + output_limit * price.output) / Decimal(1_000_000)
        with self._lock:
            if self.revoked:
                return 'session token revoked'
            if self.spent + self.reserved + worst > self.cap:
                return 'spend cap reached'
            self.reserved += worst
        return worst

    def _settle(self, reservation: Decimal, actual: Decimal | None) -> Decimal:
        charge = reservation if actual is None else actual
        with self._lock:
            self.reserved -= reservation
            self.spent += charge
        return charge

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

            def log_message(self, *_args):
                pass

            def refuse(self, status: int, reason: str, **fields):
                proxy._record(path=self.path, status=status, refused=reason, **fields)
                data = json.dumps(dict(type='error', error=dict(type='curator_proxy', message=reason))).encode()
                self.send_response(status)
                self.send_header('content-type', 'application/json')
                self.send_header('content-length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self.refuse(404, 'route not allowed')

            def do_POST(self):
                path = urlsplit(self.path).path
                if not hmac.compare_digest(proxy.provider.presented(self.headers).encode(), proxy.token.encode()):
                    return self.refuse(401, 'unknown session token')
                if path not in proxy.provider.routes:
                    return self.refuse(404, 'route not allowed')
                try:
                    length = int(self.headers.get('content-length', '-1'))
                except ValueError:
                    length = -1
                if not (0 <= length <= MAX_BODY):
                    return self.refuse(413, 'body length missing or too large')
                body = self.rfile.read(length)
                try:
                    request = json.loads(body)
                    model = request['model']
                    output_limit = int(request.get(proxy.provider.output_field) or 0)
                except (ValueError, KeyError, TypeError):
                    return self.refuse(400, 'request must be JSON with a model and an output limit')
                reservation = proxy._reserve(model, body, output_limit)
                if isinstance(reservation, str):
                    return self.refuse(429, reservation, model=model)
                status, received, actual = 502, b'', None
                try:
                    status, received = self.forward(path, body)
                    usage = usage_of(proxy.provider, received)
                    actual = None if usage is None else cost_of(proxy.provider, proxy.prices[model], usage)
                except OSError as error:
                    if not received:
                        self.refuse(502, f'upstream unreachable: {type(error).__name__}')
                finally:
                    charge = proxy._settle(reservation, actual)
                    proxy._record(path=path, model=model, status=status, reserved=reservation,
                                  charged=charge, usage_missing=actual is None)

            def forward(self, path: str, body: bytes) -> tuple[int, bytes]:
                up = proxy.upstream
                connection_type = http.client.HTTPSConnection if up.scheme == 'https' else http.client.HTTPConnection
                connection = connection_type(up.hostname, up.port, timeout=600)
                headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_HEADERS}
                name, value = proxy.provider.auth(proxy._key)
                headers[name] = value
                headers['content-length'] = str(len(body))
                try:
                    connection.request('POST', path, body=body, headers=headers)
                    response = connection.getresponse()
                    self.send_response(response.status)
                    for k, v in response.getheaders():
                        if k.lower() not in HOP_HEADERS:
                            self.send_header(k, v)
                    self.send_header('transfer-encoding', 'chunked')
                    self.end_headers()
                    received = bytearray()
                    while chunk := response.read1(65536):
                        received += chunk
                        self.wfile.write(b'%x\r\n%s\r\n' % (len(chunk), chunk))
                        self.wfile.flush()
                    self.wfile.write(b'0\r\n\r\n')
                    return response.status, bytes(received)
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
