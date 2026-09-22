"""Tests for RDAP domain-age lookups, using httpx.MockTransport (no network)."""

from datetime import UTC, datetime

import httpx
import pytest

from app.checks import rdap

NOW = datetime(2026, 9, 22, tzinfo=UTC)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _rdap_payload(date: str) -> dict:
    return {"events": [{"eventAction": "last changed", "eventDate": "2026-01-01T00:00:00Z"},
                       {"eventAction": "registration", "eventDate": date}]}


async def test_age_from_registration_event() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://rdap.org/domain/new-scam.xyz"
        return httpx.Response(200, json=_rdap_payload("2026-09-12T08:00:00Z"))

    async with _client(handler) as client:
        assert await rdap.fetch_domain_age(client, "new-scam.xyz", NOW) == 9


async def test_follows_bootstrap_redirect() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "rdap.org":
            return httpx.Response(302, headers={"Location": "https://rdap.registry.test/domain/old.com"})
        return httpx.Response(200, json=_rdap_payload("2000-09-22T00:00:00Z"))

    async with _client(handler) as client:
        assert await rdap.fetch_domain_age(client, "old.com", NOW) > 9000


@pytest.mark.parametrize("bad", ["../../admin", "a b.com", "evil.com/x?y", "-bad.com", "x"])
def test_normalize_rejects_invalid_domains(bad: str) -> None:
    with pytest.raises(rdap.RdapError):
        rdap.normalize_domain(bad)


def test_normalize_idn_to_punycode() -> None:
    assert rdap.normalize_domain("Bücher.DE") == "xn--bcher-kva.de"


async def test_batch_reports_failures_as_skipped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.rsplit("/", 1)[-1]
        if name == "ok.com":
            return httpx.Response(200, json=_rdap_payload("2026-09-01T00:00:00Z"))
        if name == "missing.in":
            return httpx.Response(404)
        if name == "noevent.com":
            return httpx.Response(200, json={"events": []})
        raise httpx.ConnectTimeout("timeout", request=request)

    async with _client(handler) as client:
        ages, skipped = await rdap.check_domain_ages(
            client, ["ok.com", "missing.in", "noevent.com", "slow.com"], NOW
        )
    assert ages == {"ok.com": 21}
    assert [s.check for s in skipped] == [
        "Domain age (missing.in)", "Domain age (noevent.com)", "Domain age (slow.com)"
    ]
    assert "ConnectTimeout" in skipped[-1].reason


async def test_batch_caps_number_of_lookups() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=_rdap_payload("2020-01-01T00:00:00Z"))

    async with _client(handler) as client:
        await rdap.check_domain_ages(client, [f"d{i}.com" for i in range(20)], NOW)
    assert len(calls) == rdap.MAX_RDAP_LOOKUPS
