"""End-to-end tests of the deterministic checks on the built-in samples (offline)."""

import httpx

from app.checks.runner import network_facts, parse_input, rdap_targets, static_facts
from app.models import RiskBand
from app.samples import get_sample
from app.scoring import score_scan


def _offline_score(sample_id: str):
    return score_scan(static_facts(parse_input(get_sample(sample_id).text)))


def test_obvious_scam_is_high_risk_without_any_api() -> None:
    result = _offline_score("obvious_scam")
    assert result.score >= 70
    assert {"payment_demand", "lookalike_domain", "free_email"} <= {h.id for h in result.breakdown}


def test_rental_scam_is_high_risk_without_any_api() -> None:
    assert _offline_score("rental_scam").band is RiskBand.HIGH


def test_subtle_scam_is_at_least_suspicious_without_any_api() -> None:
    assert _offline_score("subtle_scam").score >= 30


def test_legitimate_offer_is_low_without_any_api() -> None:
    assert _offline_score("legitimate").score <= 25


def test_parse_input_includes_submitted_url_and_extras() -> None:
    parsed = parse_input("hi", "https://x.example.com/a", extra_emails=["HR@Foo.in"])
    assert parsed.urls == ["https://x.example.com/a"]
    assert parsed.emails == ["hr@foo.in"]
    assert parsed.domains == ["example.com", "foo.in"]


def test_rdap_skips_free_mail_shorteners_and_official_domains() -> None:
    parsed = parse_input("a@gmail.com https://bit.ly/x https://infosys.com new-site.xyz")
    assert rdap_targets(parsed) == ["new-site.xyz"]


async def test_network_facts_merges_rdap_and_safe_browsing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "rdap.org":
            return httpx.Response(200, json={"events": [
                {"eventAction": "registration", "eventDate": "2099-01-01T00:00:00Z"}
            ]})
        return httpx.Response(200, json={})

    parsed = parse_input(get_sample("obvious_scam").text)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        facts = await network_facts(client, parsed, safe_browsing_key=None)
    assert facts.domain_ages == {"tcs-careers.xyz": 0}  # future date clamps to 0
    assert [s.check for s in facts.skipped_checks] == ["Google Safe Browsing"]
