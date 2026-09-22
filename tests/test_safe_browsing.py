"""Tests for the Safe Browsing client, using httpx.MockTransport (no network)."""

import json

import httpx

from app.checks import safe_browsing as sb


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_flagged_url_reported_and_key_sent_in_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "test-key"
        assert "key=" not in str(request.url)  # key never in the URL
        body = json.loads(request.content)
        assert body["threatInfo"]["threatEntries"] == [
            {"url": "http://evil.xyz/login"}, {"url": "https://ok.com"}
        ]
        return httpx.Response(200, json={"matches": [
            {"threatType": "SOCIAL_ENGINEERING", "threat": {"url": "http://evil.xyz/login"}}
        ]})

    async with _client(handler) as client:
        hits, skipped = await sb.check_urls(client, "test-key", ["evil.xyz/login", "https://ok.com"])
    assert hits == ["http://evil.xyz/login flagged as SOCIAL_ENGINEERING"]
    assert skipped == []


async def test_empty_response_means_clean() -> None:
    async with _client(lambda r: httpx.Response(200, json={})) as client:
        assert await sb.check_urls(client, "k", ["https://ok.com"]) == ([], [])


async def test_missing_key_is_skipped_without_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call the API without a key")

    async with _client(handler) as client:
        hits, skipped = await sb.check_urls(client, None, ["https://ok.com"])
    assert hits == []
    assert skipped[0].check == sb.CHECK_NAME and "not configured" in skipped[0].reason


async def test_no_urls_no_call_no_skip() -> None:
    async with _client(lambda r: httpx.Response(500)) as client:
        assert await sb.check_urls(client, "k", []) == ([], [])


async def test_api_error_and_timeout_are_skipped() -> None:
    async with _client(lambda r: httpx.Response(403)) as client:
        _, skipped = await sb.check_urls(client, "k", ["https://a.com"])
    assert "HTTP 403" in skipped[0].reason

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    async with _client(timeout) as client:
        _, skipped = await sb.check_urls(client, "k", ["https://a.com"])
    assert "ReadTimeout" in skipped[0].reason
