"""Scan orchestration: gather facts from every source, then score them.

    URL ──> SSRF-safe fetch of the linked page (optional), appended to text
    text ─┬─> regex parse ─> RDAP + Safe Browsing ─┐   (concurrent)
          └─> Gemini extraction ───────────────────┤
                                                   v
          static checks (uses Gemini company_name) ─> merge ─> score_scan()
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import BaseModel

from app.checks.runner import network_facts, parse_input, static_facts
from app.extractor import ExtractedOffer, GeminiExtractor, facts_from_extraction
from app.models import ScanFacts, ScoreResult, SkippedCheck
from app.scoring import score_scan
from app.security import FetchError

MAX_HIGHLIGHTS = 30
LINKED_PAGE_MARKER = "----- Text of the linked page -----"
FETCH_CHECK_NAME = "Linked page content"

PageFetcher = Callable[[str], Awaitable[str]]


class ScanReport(BaseModel):
    """Everything the UI needs to render a scan."""

    result: ScoreResult
    analyzed_text: str
    highlights: list[str]
    company_name: str | None
    urls: list[str]
    emails: list[str]
    ai_extraction_used: bool


def merge_facts(*parts: ScanFacts) -> ScanFacts:
    """Combine facts from several sources.

    Lists are concatenated and de-duplicated in order; for tri-state fields
    the first non-None value wins; domain ages are unioned.
    """
    merged: dict[str, Any] = {}
    for name, field in ScanFacts.model_fields.items():
        values = [getattr(p, name) for p in parts]
        if field.annotation == dict[str, int]:
            merged[name] = {k: v for d in values for k, v in d.items()}
        elif isinstance(values[0], list):
            flat = [item for v in values for item in v]
            merged[name] = flat if name == "skipped_checks" else list(dict.fromkeys(flat))
        else:
            merged[name] = next((v for v in values if v is not None), None)
    return ScanFacts(**merged)


def collect_highlights(text: str, facts: ScanFacts, extracted: ExtractedOffer | None) -> list[str]:
    """Exact substrings of the input the UI should highlight."""
    candidates = (
        facts.payment_demand_evidence
        + facts.untraceable_payment_evidence
        + facts.sensitive_document_evidence
        + facts.urgency_phrases
    )
    if extracted:
        candidates += extracted.suspicious_quotes
        if extracted.unrealistic_salary and extracted.salary_quote:
            candidates.append(extracted.salary_quote)
    found = [c for c in dict.fromkeys(candidates) if c and c in text]
    return found[:MAX_HIGHLIGHTS]


async def _with_linked_page(
    text: str, url: str | None, fetcher: PageFetcher | None
) -> tuple[str, list[SkippedCheck]]:
    """Append the linked page's visible text, if a fetcher is configured."""
    if not url or fetcher is None:
        return text, []
    try:
        page = await fetcher(url)
    except FetchError as exc:
        return text, [SkippedCheck(check=FETCH_CHECK_NAME, reason=str(exc))]
    if not page.strip():
        return text, []
    return f"{text}\n\n{LINKED_PAGE_MARKER}\n{page}".strip(), []


async def run_scan(
    text: str,
    submitted_url: str | None,
    extractor: GeminiExtractor,
    http_client: httpx.AsyncClient,
    safe_browsing_key: str | None,
    page_fetcher: PageFetcher | None = None,
) -> ScanReport:
    """Run every check and return the scored report. Never raises for
    external-service failures; those appear in `skipped_checks`."""
    text, fetch_skipped = await _with_linked_page(text, submitted_url, page_fetcher)
    parsed = parse_input(text, submitted_url)
    (extracted, ai_skipped), net = await asyncio.gather(
        extractor.extract(text) if text.strip() else _no_text(),
        network_facts(http_client, parsed, safe_browsing_key),
    )

    company_name = extracted.company_name if extracted else None
    if extracted:
        # Add anything Gemini found that the regex missed (already grounded).
        parsed = parse_input(text, submitted_url, extracted.sender_emails, extracted.domains)
    ai_facts = facts_from_extraction(extracted) if extracted else ScanFacts()

    facts = merge_facts(
        ai_facts,
        static_facts(parsed, company_name),
        net,
        ScanFacts(skipped_checks=fetch_skipped + ai_skipped),
    )
    return ScanReport(
        result=score_scan(facts),
        analyzed_text=text,
        highlights=collect_highlights(text, facts, extracted),
        company_name=company_name,
        urls=parsed.urls,
        emails=parsed.emails,
        ai_extraction_used=extracted is not None,
    )


async def _no_text() -> tuple[None, list[SkippedCheck]]:
    """URL-only scans have nothing for Gemini to read."""
    return None, []
