"""Domain age lookup via RDAP (the JSON successor to WHOIS).

Uses the public bootstrap service https://rdap.org/domain/<domain>, which
redirects to the authoritative registry's RDAP server. No API key needed.
The registration date is the ``eventDate`` of the event whose
``eventAction`` is ``"registration"`` (RFC 9083).
"""

import asyncio
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.models import SkippedCheck

RDAP_BASE_URL = "https://rdap.org/domain/"
RDAP_TIMEOUT_SECONDS = 8.0  # .in (NIXI) lookups measured at ~4s via the redirect
MAX_RDAP_LOOKUPS = 5
_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}$")


class RdapError(Exception):
    """Lookup failed or returned no usable registration date."""


def normalize_domain(domain: str) -> str:
    """Lower-case, IDNA-encode and validate a domain before it enters a URL path.

    Raises:
        RdapError: If the value is not a syntactically valid domain name.
    """
    try:
        ascii_domain = domain.strip().rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise RdapError(f"invalid domain {domain!r}") from exc
    if not _DOMAIN_RE.fullmatch(ascii_domain):
        raise RdapError(f"invalid domain {domain!r}")
    return ascii_domain


def parse_registration_date(payload: dict[str, Any]) -> datetime:
    """Extract the registration timestamp from an RDAP domain response."""
    for event in payload.get("events", []):
        if event.get("eventAction") == "registration" and event.get("eventDate"):
            parsed = datetime.fromisoformat(event["eventDate"])
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    raise RdapError("no registration event in RDAP response")


async def fetch_domain_age(
    client: httpx.AsyncClient, domain: str, now: datetime | None = None
) -> int:
    """Return the domain's age in whole days.

    Raises:
        RdapError: On invalid input, HTTP/network failure or missing data.
    """
    safe_domain = normalize_domain(domain)
    try:
        response = await client.get(
            RDAP_BASE_URL + safe_domain,
            headers={"Accept": "application/rdap+json"},
            timeout=RDAP_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        raise RdapError(f"network error: {type(exc).__name__}") from exc
    if response.status_code == 404:
        raise RdapError("no RDAP record (domain unregistered or TLD has no RDAP service)")
    if response.status_code != 200:
        raise RdapError(f"RDAP returned HTTP {response.status_code}")
    try:
        registered = parse_registration_date(response.json())
    except ValueError as exc:  # bad JSON or bad date
        raise RdapError("unparseable RDAP response") from exc
    current = now or datetime.now(UTC)
    return max((current - registered).days, 0)


async def check_domain_ages(
    client: httpx.AsyncClient, domains: list[str], now: datetime | None = None
) -> tuple[dict[str, int], list[SkippedCheck]]:
    """Look up several domains concurrently.

    Returns:
        (domain -> age in days, checks that were skipped with reasons).
        A failed lookup never raises; it is reported as skipped.
    """
    targets = domains[:MAX_RDAP_LOOKUPS]
    results = await asyncio.gather(
        *(fetch_domain_age(client, d, now) for d in targets), return_exceptions=True
    )
    ages: dict[str, int] = {}
    skipped: list[SkippedCheck] = []
    for domain, result in zip(targets, results, strict=True):
        if isinstance(result, int):
            ages[domain] = result
        elif isinstance(result, RdapError):
            skipped.append(SkippedCheck(check=f"Domain age ({domain})", reason=str(result)))
        else:
            skipped.append(SkippedCheck(check=f"Domain age ({domain})", reason="unexpected error"))
    return ages, skipped
