"""HTTP hardening: security headers, request-body cap and per-IP rate limiting."""

import time
from collections import deque

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Strict CSP: the page ships no inline script or style (enforced by tests).
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'none'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}


class SecurityHeadersMiddleware:
    """Add security headers to every response; `no-store` on API responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._headers = [(k.lower().encode(), v.encode()) for k, v in SECURITY_HEADERS.items()]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = scope["path"].startswith("/api/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = {name for name, _ in message.get("headers", [])}
                extra = [h for h in self._headers if h[0] not in existing]
                if is_api:
                    extra.append((b"cache-control", b"no-store"))
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        await self.app(scope, receive, send_with_headers)


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Reject request bodies over `max_bytes` with 413, before they are parsed.

    Checks `Content-Length` up front and also counts streamed bytes, so a
    chunked upload without a length header cannot bypass the limit.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope.get("headers", [])).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            await _plain_response(send, 413, b'{"detail":"Request body too large"}')
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await _plain_response(send, 413, b'{"detail":"Request body too large"}')


async def _plain_response(send: Send, status: int, body: bytes) -> None:
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
    })
    await send({"type": "http.response.body", "body": body})


class RateLimiter:
    """In-memory sliding-window limiter: `limit` requests per `window` seconds per key.

    State is per process (per Cloud Run instance), which is enough to stop a
    single client from burning Gemini / Safe Browsing quota. A shared store
    (e.g. Memorystore) would be needed for a global limit.
    """

    MAX_TRACKED_KEYS = 10_000

    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, now: float | None = None) -> float | None:
        """Record a request. Returns None if allowed, else seconds until retry.

        No `await` inside, so it is atomic on the asyncio event loop.
        """
        now = time.monotonic() if now is None else now
        cutoff = now - self.window
        hits = self._hits.get(key)
        if hits is None:
            if len(self._hits) >= self.MAX_TRACKED_KEYS:
                self._prune(cutoff)
            hits = self._hits[key] = deque()
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.limit:
            return max(hits[0] + self.window - now, 1.0)
        hits.append(now)
        return None

    def _prune(self, cutoff: float) -> None:
        """Drop idle keys; if still full, drop the oldest half (bounded memory)."""
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
            del self._hits[key]
        if len(self._hits) >= self.MAX_TRACKED_KEYS:
            oldest = sorted(self._hits, key=lambda k: self._hits[k][-1])
            for key in oldest[: len(oldest) // 2]:
                del self._hits[key]


def client_ip(peer: str | None, forwarded_for: str | None, trusted_proxies: int) -> str:
    """Determine the client IP for rate limiting.

    With `trusted_proxies = N > 0`, take the N-th entry from the *right* of
    X-Forwarded-For: entries further left are client-supplied and spoofable.
    With 0 (default) the header is ignored and the TCP peer is used.
    """
    if trusted_proxies > 0 and forwarded_for:
        hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
        if len(hops) >= trusted_proxies:
            return hops[-trusted_proxies]
    return peer or "unknown"
