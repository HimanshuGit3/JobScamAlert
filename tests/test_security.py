"""SSRF protection tests for the user-URL fetcher (fake DNS + MockTransport, no network)."""

import httpx
import pytest

from app import security
from app.security import FetchError, fetch_page_text, html_to_text, is_public_ip, validate_url

PUBLIC_IP = "93.184.215.14"


def resolver_for(mapping: dict[str, list[str]]):
    """Fake DNS: hostname -> addresses."""

    async def resolve(host: str, port: int) -> list[str]:
        if host not in mapping:
            raise FetchError("could not resolve host")
        return mapping[host]

    return resolve


PUBLIC_DNS = resolver_for({"example.com": [PUBLIC_IP], "other.example": [PUBLIC_IP]})


def html_response(body: str = "<p>Hello</p>", **headers: str) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8", **headers}, text=body)


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1",
     "0.0.0.0",  # noqa: S104 - an address under test, not a bind
     "224.0.0.1", "255.255.255.255", "::1", "fe80::1", "fc00::1",
     "::ffff:127.0.0.1", "::ffff:10.0.0.1", "2002:7f00:1::", "2001::1"],
)
def test_non_public_addresses_blocked(address: str) -> None:
    assert not is_public_ip(address)


@pytest.mark.parametrize("address", [PUBLIC_IP, "8.8.8.8", "2606:4700:4700::1111"])
def test_public_addresses_allowed(address: str) -> None:
    assert is_public_ip(address)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",      # cloud metadata
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://10.0.0.5/admin",
        "ftp://example.com/file",
        "file:///etc/passwd",
        "gopher://example.com/",
        "http://user:pass@example.com/",
        "http://example.com:8080/",
        "https://example.com:22/",
        "http:///nohost",
        "http://[::1/",                                  # malformed
    ],
)
async def test_validate_url_rejects(url: str) -> None:
    with pytest.raises(FetchError):
        await validate_url(url, PUBLIC_DNS)


async def test_hostname_resolving_to_private_ip_blocked() -> None:
    dns = resolver_for({"internal.attacker.test": ["10.0.0.7"]})
    with pytest.raises(FetchError, match="private"):
        await validate_url("http://internal.attacker.test/", dns)


async def test_mixed_public_and_private_records_blocked() -> None:
    dns = resolver_for({"rebind.attacker.test": [PUBLIC_IP, "127.0.0.1"]})
    with pytest.raises(FetchError, match="private"):
        await validate_url("https://rebind.attacker.test/", dns)


async def test_validate_url_pins_to_checked_ip() -> None:
    target = await validate_url("https://Example.com./jobs?id=1#frag", PUBLIC_DNS)
    assert target.pinned_url == f"https://{PUBLIC_IP}/jobs?id=1"
    assert target.host_header == "example.com"
    assert target.hostname == "example.com"


async def test_fetch_connects_to_pinned_ip_with_original_host_and_sni() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return html_response("<html><head><title>x</title><script>evil()</script></head>"
                             "<body><h1>Offer</h1><p>Pay &#8377;500 now</p>"
                             '<a href="https://pay.example/upi">link</a></body></html>')

    text = await fetch_page_text("https://example.com/offer", PUBLIC_DNS, httpx.MockTransport(handler))
    request = seen[0]
    assert request.url.host == PUBLIC_IP
    assert request.headers["host"] == "example.com"
    assert request.extensions["sni_hostname"] == "example.com"
    assert "Pay ₹500 now" in text and "https://pay.example/upi" in text
    assert "evil" not in text and "<" not in text


async def test_redirect_to_private_ip_blocked_before_request() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/"})

    with pytest.raises(FetchError, match="private"):
        await fetch_page_text("http://example.com/", PUBLIC_DNS, httpx.MockTransport(handler))
    assert seen == [f"http://{PUBLIC_IP}/"]  # the metadata IP was never contacted


async def test_redirects_are_revalidated_and_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers["host"] == "example.com":
            return httpx.Response(301, headers={"location": "https://other.example/final"})
        return html_response("<p>Final page</p>")

    assert await fetch_page_text("http://example.com/", PUBLIC_DNS, httpx.MockTransport(handler)) == "Final page"


async def test_redirect_loop_stops() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"location": "/again"})

    with pytest.raises(FetchError, match="too many redirects"):
        await fetch_page_text("http://example.com/", PUBLIC_DNS, httpx.MockTransport(handler))
    assert calls == security.MAX_REDIRECTS + 1


async def test_declared_oversized_body_rejected() -> None:
    transport = httpx.MockTransport(lambda r: html_response(
        "x", **{"content-length": str(security.MAX_BODY_BYTES + 1)}))
    with pytest.raises(FetchError, match="too large"):
        await fetch_page_text("http://example.com/", PUBLIC_DNS, transport)


async def test_streamed_oversized_body_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        big = b"a" * (security.MAX_BODY_BYTES + 10)
        return httpx.Response(200, headers={"content-type": "text/plain"},
                              stream=httpx.ByteStream(big))  # no content-length check possible

    with pytest.raises(FetchError, match="too large"):
        await fetch_page_text("http://example.com/", PUBLIC_DNS, httpx.MockTransport(handler))


@pytest.mark.parametrize("content_type", ["application/octet-stream", "image/png", "application/pdf"])
async def test_non_text_content_rejected(content_type: str) -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, headers={"content-type": content_type}, content=b"x"))
    with pytest.raises(FetchError, match="not HTML"):
        await fetch_page_text("http://example.com/", PUBLIC_DNS, transport)


async def test_http_error_status_and_network_errors_become_fetch_errors() -> None:
    with pytest.raises(FetchError, match="HTTP 404"):
        await fetch_page_text("http://example.com/", PUBLIC_DNS, httpx.MockTransport(lambda r: httpx.Response(404)))

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(FetchError, match="network error"):
        await fetch_page_text("http://example.com/", PUBLIC_DNS, httpx.MockTransport(boom))


async def test_page_text_is_truncated() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(
        200, headers={"content-type": "text/plain"}, text="y" * (security.MAX_PAGE_TEXT_CHARS + 500)))
    text = await fetch_page_text("http://example.com/", PUBLIC_DNS, transport)
    assert len(text) == security.MAX_PAGE_TEXT_CHARS


def test_html_to_text_strips_markup_and_hidden_content() -> None:
    html = "<style>p{}</style><p>Line  one</p><noscript>no</noscript><div>Line&nbsp;two</div>"
    assert html_to_text(html) == "Line one\nLine two"
