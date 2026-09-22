"""Runs all deterministic checks and returns their results as `ScanFacts`.

Split in two so the pipeline can overlap work:
* `network_facts` (RDAP + Safe Browsing) needs only the parsed URLs/emails,
  so it can run concurrently with Gemini extraction.
* `static_facts` is instant and runs after Gemini, because the company-name
  mismatch check benefits from Gemini's `company_name`.
"""

import asyncio
from dataclasses import dataclass

import httpx

from app.checks import domains as dom
from app.checks import text_parse as tp
from app.checks.data import FREE_EMAIL_PROVIDERS, KNOWN_BRANDS, URL_SHORTENERS
from app.checks.rdap import MAX_RDAP_LOOKUPS, check_domain_ages
from app.checks.safe_browsing import check_urls
from app.models import ScanFacts


@dataclass(frozen=True)
class ParsedInput:
    """URLs, emails and registrable domains found in the submission."""

    text: str
    urls: list[str]
    emails: list[str]
    domains: list[str]


def parse_input(
    text: str,
    submitted_url: str | None = None,
    extra_emails: list[str] | None = None,
    extra_urls: list[str] | None = None,
) -> ParsedInput:
    """Extract URLs, emails and domains from text plus any explicit URL.

    `extra_emails` / `extra_urls` let the pipeline add items Gemini found
    that the regex missed.
    """
    urls = ([submitted_url] if submitted_url else []) + tp.extract_urls(text) + (extra_urls or [])
    emails = tp.extract_emails(text) + [e.lower() for e in (extra_emails or [])]
    hosts = [dom.host_of(u) for u in urls] + [dom.email_domain(e) for e in emails]
    domains = [d for d in (dom.registrable_domain(h) for h in hosts if h) if d]
    return ParsedInput(
        text=text,
        urls=list(dict.fromkeys(urls))[: tp.MAX_ITEMS],
        emails=list(dict.fromkeys(emails))[: tp.MAX_ITEMS],
        domains=list(dict.fromkeys(domains))[: tp.MAX_ITEMS],
    )


def rdap_targets(parsed: ParsedInput) -> list[str]:
    """Domains worth an age lookup: skip free-mail providers, shorteners and
    official brand domains (all known to be old)."""
    candidates = [
        d for d in parsed.domains
        if d not in FREE_EMAIL_PROVIDERS
        and d not in URL_SHORTENERS
        and not any(dom.is_official_domain(d, b) for b in KNOWN_BRANDS)
    ]
    return candidates[:MAX_RDAP_LOOKUPS]


def static_facts(parsed: ParsedInput, company_name: str | None = None) -> ScanFacts:
    """All offline checks: regex red flags and domain heuristics."""
    return ScanFacts(
        payment_demand_evidence=tp.detect_payment_demands(parsed.text),
        untraceable_payment_evidence=tp.detect_untraceable_payment(parsed.text),
        sensitive_document_evidence=tp.detect_sensitive_document_requests(parsed.text),
        urgency_phrases=tp.detect_urgency(parsed.text),
        free_email_senders=dom.find_free_email_senders(parsed.emails),
        company_domain_mismatch=dom.find_company_domain_mismatch(
            company_name, parsed.text, parsed.emails
        ),
        lookalike_domains=dom.find_lookalike_domains(parsed.domains),
        suspicious_tld_domains=dom.find_suspicious_tlds(parsed.domains),
        shortener_urls=dom.find_shorteners(parsed.urls),
        insecure_urls=dom.find_insecure_urls(parsed.urls),
    )


async def network_facts(
    client: httpx.AsyncClient, parsed: ParsedInput, safe_browsing_key: str | None
) -> ScanFacts:
    """RDAP domain ages and Safe Browsing verdicts, fetched concurrently.

    Never raises; every failure becomes a `SkippedCheck`.
    """
    (ages, rdap_skipped), (matches, sb_skipped) = await asyncio.gather(
        check_domain_ages(client, rdap_targets(parsed)),
        check_urls(client, safe_browsing_key, parsed.urls),
    )
    return ScanFacts(
        domain_ages=ages,
        safe_browsing_matches=matches,
        skipped_checks=rdap_skipped + sb_skipped,
    )
