"""URL reputation via the Google Safe Browsing Lookup API (v4).

POST https://safebrowsing.googleapis.com/v4/threatMatches:find
An empty JSON object means no URL matched; otherwise ``matches`` lists each
hit with its ``threatType`` and ``threat.url``.
The API key is sent in the ``x-goog-api-key`` header rather than the query
string, so it never appears in URLs or access logs.
"""

from typing import Any

import httpx

from app.models import SkippedCheck

SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
SAFE_BROWSING_TIMEOUT_SECONDS = 5.0
MAX_URLS = 20
CHECK_NAME = "Google Safe Browsing"
THREAT_TYPES = ("MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION")


def build_request_body(urls: list[str]) -> dict[str, Any]:
    """Build a threatMatches:find request body for the given URLs."""
    return {
        "client": {"clientId": "offer-letter-inspector", "clientVersion": "1.0.0"},
        "threatInfo": {
            "threatTypes": list(THREAT_TYPES),
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url} for url in urls],
        },
    }


def _with_scheme(url: str) -> str:
    """Safe Browsing expects full URLs; bare domains get ``http://``."""
    return url if "://" in url else f"http://{url}"


async def check_urls(
    client: httpx.AsyncClient, api_key: str | None, urls: list[str]
) -> tuple[list[str], list[SkippedCheck]]:
    """Check URLs against Safe Browsing.

    Returns:
        (evidence strings for flagged URLs, skipped checks). Never raises:
        missing key, timeouts and API errors are reported as skipped.
    """
    if not urls:
        return [], []
    if not api_key:
        return [], [SkippedCheck(check=CHECK_NAME, reason="SAFE_BROWSING_API_KEY is not configured")]

    targets = [_with_scheme(u) for u in urls[:MAX_URLS]]
    try:
        response = await client.post(
            SAFE_BROWSING_URL,
            json=build_request_body(targets),
            headers={"x-goog-api-key": api_key},
            timeout=SAFE_BROWSING_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        return [], [SkippedCheck(check=CHECK_NAME, reason=f"network error: {type(exc).__name__}")]
    if response.status_code != 200:
        return [], [SkippedCheck(check=CHECK_NAME, reason=f"API returned HTTP {response.status_code}")]
    try:
        matches = response.json().get("matches", [])
    except ValueError:
        return [], [SkippedCheck(check=CHECK_NAME, reason="unparseable API response")]

    evidence = [
        f"{m.get('threat', {}).get('url', '?')} flagged as {m.get('threatType', 'UNKNOWN')}"
        for m in matches
    ]
    return list(dict.fromkeys(evidence)), []
