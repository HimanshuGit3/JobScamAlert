"""SSRF-safe fetching of a user-supplied URL.

A scanner that downloads links pasted by strangers is a classic Server-Side
Request Forgery target (e.g. http://169.254.169.254/ cloud metadata). Defences:

1. Only ``http``/``https``, default ports (80/443), no ``user:pass@`` part.
2. The host is resolved *before* connecting and **every** resolved address
   must be public (no private, loopback, link-local, CGNAT, multicast,
   reserved or IPv4-mapped/6to4/Teredo tricks).
3. DNS-rebinding is closed by *pinning*: we connect to the exact IP we
   validated, sending the original ``Host`` header and using the original
   hostname for TLS SNI and certificate verification (``sni_hostname``).
4. Redirects are followed manually, max 3, and each hop is re-validated.
5. Timeouts, a 1 MB body cap, text/html or text/plain only, proxies ignored.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import urljoin, urlsplit

import httpx

MAX_REDIRECTS = 3
MAX_BODY_BYTES = 1_000_000
MAX_PAGE_TEXT_CHARS = 10_000
FETCH_TIMEOUT = httpx.Timeout(5.0)
OVERALL_FETCH_SECONDS = 12.0
ALLOWED_PORTS = {"http": 80, "https": 443}
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml+xml")
USER_AGENT = "OfferLetterInspector/1.0 (link safety scan)"

Resolver = Callable[[str, int], Awaitable[list[str]]]


class FetchError(Exception):
    """The URL was refused or could not be fetched safely."""


@dataclass(frozen=True)
class PinnedTarget:
    """A validated URL rewritten to connect to one checked IP address."""

    pinned_url: str
    host_header: str
    hostname: str


def is_public_ip(address: str) -> bool:
    """True only for globally routable unicast addresses."""
    ip = ipaddress.ip_address(address.split("%", 1)[0])  # drop IPv6 zone id
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        elif ip.sixtofour or ip.teredo:
            return False  # tunnelling formats that can embed private IPv4
    return ip.is_global and not (ip.is_multicast or ip.is_reserved)


async def resolve_host(host: str, port: int) -> list[str]:
    """Resolve a hostname to all of its IP addresses (A and AAAA)."""
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError("could not resolve host") from exc
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


async def validate_url(url: str, resolver: Resolver = resolve_host) -> PinnedTarget:
    """Check a URL against the SSRF rules and pin it to a vetted IP.

    Raises:
        FetchError: If any rule is violated.
    """
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise FetchError("malformed URL") from exc
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_PORTS:
        raise FetchError("only http and https URLs can be fetched")
    if parts.username or parts.password:
        raise FetchError("URLs with embedded credentials are not allowed")
    hostname = (parts.hostname or "").rstrip(".").lower()
    if not hostname:
        raise FetchError("URL has no host")
    if port not in (None, ALLOWED_PORTS[scheme]):
        raise FetchError("non-standard ports are not allowed")
    port = ALLOWED_PORTS[scheme]

    try:
        ipaddress.ip_address(hostname)
        addresses = [hostname]
    except ValueError:
        addresses = await resolver(hostname, port)
    if not addresses:
        raise FetchError("host has no addresses")
    # Every address must be public: an attacker controlling DNS could
    # otherwise mix a public and a private record.
    if not all(is_public_ip(a) for a in addresses):
        raise FetchError("URL points to a private or reserved network address")

    ip = ipaddress.ip_address(addresses[0].split("%", 1)[0])
    ip_host = f"[{ip}]" if ip.version == 6 else str(ip)
    path = parts.path or "/"
    query = f"?{parts.query}" if parts.query else ""
    return PinnedTarget(
        pinned_url=f"{scheme}://{ip_host}{path}{query}",
        host_header=f"[{hostname}]" if ":" in hostname else hostname,
        hostname=hostname,
    )


class _TextExtractor(HTMLParser):
    """Collect visible text, skipping script/style and similar elements."""

    _SKIP: ClassVar[frozenset[str]] = frozenset({"script", "style", "noscript", "template", "svg", "head"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._depth += 1
        elif tag == "a":
            href = dict(attrs).get("href") or ""
            if href.lower().startswith(("http://", "https://")):
                self.chunks.append(f" {href} ")  # keep link targets for URL checks

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._depth:
            self._depth -= 1
        elif tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "section"}:
            self.chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._depth:
            self.chunks.append(data)


def html_to_text(html: str) -> str:
    """Convert HTML to plain text (no scripts executed, nothing rendered)."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.chunks).splitlines())
    return "\n".join(line for line in lines if line)


async def _read_limited(response: httpx.Response) -> bytes:
    """Read the body, aborting once it exceeds MAX_BODY_BYTES."""
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise FetchError("page is too large")
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise FetchError("page is too large")
    return bytes(body)


async def _fetch(url: str, resolver: Resolver, transport: httpx.AsyncBaseTransport | None) -> str:
    current = url
    # trust_env=False: ignore proxy env vars that could route around the checks.
    # No keep-alive: a redirect must never reuse a TLS session opened for another host.
    async with httpx.AsyncClient(
        transport=transport, timeout=FETCH_TIMEOUT, follow_redirects=False, trust_env=False,
        limits=httpx.Limits(max_keepalive_connections=0),
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            target = await validate_url(current, resolver)
            request = client.build_request(
                "GET",
                target.pinned_url,
                headers={"Host": target.host_header, "User-Agent": USER_AGENT,
                         "Accept": "text/html,text/plain;q=0.9"},
                extensions={"sni_hostname": target.hostname},
            )
            response = await client.send(request, stream=True)
            try:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("redirect without a location")
                    current = urljoin(current, location)
                    continue
                if response.status_code != 200:
                    raise FetchError(f"page returned HTTP {response.status_code}")
                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise FetchError("page is not HTML or plain text")
                body = await _read_limited(response)
            finally:
                await response.aclose()
            decoded = body.decode(response.charset_encoding or "utf-8", errors="replace")
            text = html_to_text(decoded) if content_type != "text/plain" else decoded
            return text[:MAX_PAGE_TEXT_CHARS]
    raise FetchError("too many redirects")


async def fetch_page_text(
    url: str,
    resolver: Resolver = resolve_host,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Safely download a user-supplied URL and return its visible text.

    Raises:
        FetchError: With a user-presentable reason; never leaks internals.
    """
    try:
        return await asyncio.wait_for(_fetch(url, resolver, transport), OVERALL_FETCH_SECONDS)
    except FetchError:
        raise
    except TimeoutError as exc:
        raise FetchError("timed out") from exc
    except httpx.HTTPError as exc:
        raise FetchError(f"network error ({type(exc).__name__})") from exc
    except (LookupError, UnicodeError) as exc:  # unknown charset etc.
        raise FetchError("could not decode page") from exc
