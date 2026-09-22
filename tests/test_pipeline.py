"""Tests for scan orchestration with Gemini and HTTP both faked."""

import httpx

from app.models import RiskBand, ScanFacts, SkippedCheck
from app.pipeline import merge_facts, run_scan
from app.samples import get_sample
from tests.fakes import fake_extractor, make_extraction


def _http(handler=None) -> httpx.AsyncClient:
    def default(request: httpx.Request) -> httpx.Response:
        if request.url.host == "rdap.org":
            return httpx.Response(200, json={"events": [
                {"eventAction": "registration", "eventDate": "2026-09-10T00:00:00Z"}]})
        return httpx.Response(200, json={})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler or default))


def test_merge_facts_rules() -> None:
    a = ScanFacts(urgency_phrases=["now"], interview_mentioned=None, domain_ages={"a.com": 1},
                  skipped_checks=[SkippedCheck(check="x", reason="r")])
    b = ScanFacts(urgency_phrases=["now", "today"], interview_mentioned=False, domain_ages={"b.com": 2},
                  skipped_checks=[SkippedCheck(check="y", reason="r")])
    merged = merge_facts(a, b)
    assert merged.urgency_phrases == ["now", "today"]
    assert merged.interview_mentioned is False
    assert merged.domain_ages == {"a.com": 1, "b.com": 2}
    assert [s.check for s in merged.skipped_checks] == ["x", "y"]


async def test_scan_without_gemini_still_scores_and_reports_skip() -> None:
    extractor, _ = fake_extractor(error=RuntimeError("down"))
    async with _http() as client:
        report = await run_scan(get_sample("obvious_scam").text, None, extractor, client, None)
    assert report.result.band is RiskBand.HIGH
    assert not report.ai_extraction_used
    assert {s.check for s in report.result.skipped_checks} == {"Gemini extraction", "Google Safe Browsing"}
    assert "new_domain" in {h.id for h in report.result.breakdown}


async def test_gemini_facts_add_signals_regex_cannot_see() -> None:
    text = get_sample("subtle_scam").text
    extraction = make_extraction(
        company_name="Nexora Analytics Pvt. Ltd.",
        urgency_phrases=["Please confirm by Friday to secure your joining date."],
        interview_mentioned=True,
    )
    extractor, _ = fake_extractor(extraction)
    async with _http() as client:
        report = await run_scan(text, None, extractor, client, "key")
    ids = {h.id for h in report.result.breakdown}
    assert {"payment_demand", "sensitive_documents", "urgency", "new_domain"} <= ids
    assert report.ai_extraction_used and report.company_name == "Nexora Analytics Pvt. Ltd."
    assert report.result.band is RiskBand.HIGH
    assert "Please confirm by Friday to secure your joining date." in report.highlights


async def test_legitimate_sample_stays_low_with_gemini() -> None:
    extraction = make_extraction(company_name="Infosys Limited", interview_mentioned=True)
    extractor, _ = fake_extractor(extraction)
    async with _http() as client:
        report = await run_scan(get_sample("legitimate").text, None, extractor, client, "key")
    assert report.result.score <= 25
    assert report.highlights == []


async def test_highlights_are_exact_substrings() -> None:
    text = get_sample("obvious_scam").text
    extractor, _ = fake_extractor(make_extraction(suspicious_quotes=["not in text"]))
    async with _http() as client:
        report = await run_scan(text, None, extractor, client, None)
    assert report.highlights and all(h in text for h in report.highlights)


async def test_url_only_scan_skips_gemini_call() -> None:
    extractor, models = fake_extractor(make_extraction())
    async with _http() as client:
        report = await run_scan("", "http://tcs-careers.xyz/join", extractor, client, None)
    assert models.calls == []
    assert "lookalike_domain" in {h.id for h in report.result.breakdown}
