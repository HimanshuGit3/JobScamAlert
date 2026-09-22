"""Offline domain and URL heuristics.

Free-email senders, company/domain mismatch, typosquat / look-alike brand
domains, suspicious TLDs, URL shorteners and plain-HTTP links.
"""

import ipaddress
import re
from urllib.parse import urlsplit

from app.checks.data import (
    COMPANY_STOPWORDS,
    FREE_EMAIL_PROVIDERS,
    KNOWN_BRANDS,
    MULTI_PART_SUFFIXES,
    SUSPICIOUS_TLDS,
    URL_SHORTENERS,
    Brand,
)

# Common character substitutions used in look-alike domains.
_HOMOGLYPHS = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "$": "s"})
_SHORT_TOKEN_LEN = 5  # tokens this short must match a whole hyphen-separated part
_PRODUCT_MENTION_RE = re.compile(
    r"\b(?:google\s+(?:meet|pay|play|forms?|drive|docs|maps|chrome)|gmail|"
    r"microsoft\s+(?:teams|word|excel|office|forms)|amazon\s+pay|"
    r"paytm\s+(?:app|wallet)|jio\s*(?:meet|sim))\b",
    re.IGNORECASE,
)
# One precompiled whole-word pattern per brand, built once at import instead of
# compiling a regex per alias on every call.
_BRAND_ALIAS_RES: tuple[tuple[Brand, re.Pattern[str]], ...] = tuple(
    (brand, re.compile(r"\b(?:" + "|".join(re.escape(a) for a in brand.aliases) + r")\b"))
    for brand in KNOWN_BRANDS
)


def host_of(url: str) -> str | None:
    """Return the lower-case host of a URL; scheme-less input is allowed."""
    candidate = url if "://" in url else f"http://{url}"
    try:
        host = urlsplit(candidate).hostname
    except ValueError:
        return None
    return host.rstrip(".").lower() if host else None


def registrable_domain(host: str) -> str | None:
    """Reduce a host to its registrable domain (``a.b.tcs.com`` -> ``tcs.com``).

    Returns None for IP addresses and single-label hosts.
    """
    host = host.rstrip(".").lower()
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    labels = host.split(".")
    if len(labels) < 2:
        return None
    take = 3 if ".".join(labels[-2:]) in MULTI_PART_SUFFIXES and len(labels) >= 3 else 2
    return ".".join(labels[-take:])


def tld_of(domain: str) -> str:
    """Last label of a domain."""
    return domain.rsplit(".", 1)[-1]


def email_domain(email: str) -> str:
    """Lower-case domain part of an email address."""
    return email.rsplit("@", 1)[-1].lower()


def _label(domain: str) -> str:
    """Registrable domain without its public suffix (``tcs-careers.co.in`` -> ``tcs-careers``)."""
    return domain.split(".", 1)[0]


def levenshtein(a: str, b: str) -> int:
    """Classic edit distance (insert / delete / substitute), O(len(a)*len(b))."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (char_a != char_b),
            ))
        previous = current
    return previous[-1]


def is_official_domain(domain: str, brand: Brand) -> bool:
    """True if `domain` is (a subdomain of) one of the brand's official domains."""
    return any(domain == d or domain.endswith(f".{d}") for d in brand.domains)


def _is_official_anywhere(domain: str) -> bool:
    return any(is_official_domain(domain, brand) for brand in KNOWN_BRANDS)


def _imitates(label: str, token: str) -> bool:
    """Does a domain label imitate a brand token?

    Matches (1) the token as a whole hyphen-separated part
    (``tcs-careers``), (2) for longer tokens, the token embedded anywhere
    (``infosyscareers``), (3) homoglyph swaps (``inf0sys``), or
    (4) a small edit distance (``infosis``, ``accentrue``).
    """
    parts = label.split("-")
    if token in parts:
        return True
    compact = label.replace("-", "")
    if len(token) > _SHORT_TOKEN_LEN and token in compact:
        return True
    deglyphed = compact.translate(_HOMOGLYPHS)
    if deglyphed == token or (len(token) > _SHORT_TOKEN_LEN and token in deglyphed):
        return True
    if len(token) >= _SHORT_TOKEN_LEN:
        allowed = 2 if len(token) >= 8 else 1
        # Edit distance is at least the length gap: skip the O(n*m) DP when it can't match.
        if abs(len(compact) - len(token)) > allowed:
            return False
        return 0 < levenshtein(compact, token) <= allowed
    return False


def find_lookalike_domains(domains: list[str]) -> list[str]:
    """Domains that imitate a known employer without belonging to it."""
    hits: list[str] = []
    for domain in domains:
        if _is_official_anywhere(domain) or domain in FREE_EMAIL_PROVIDERS:
            continue
        label = _label(domain)
        for brand in KNOWN_BRANDS:
            if any(_imitates(label, token) for token in brand.tokens):
                hits.append(f"{domain} imitates {brand.name} (official: {', '.join(brand.domains)})")
                break
    return hits


def find_free_email_senders(emails: list[str]) -> list[str]:
    """Emails hosted by a free consumer provider (Gmail, Yahoo, Outlook...)."""
    return [
        f"{email} uses free provider {email_domain(email)}"
        for email in emails
        if email_domain(email) in FREE_EMAIL_PROVIDERS
    ]


def brands_mentioned(text: str) -> list[Brand]:
    """Known brands whose name appears in the text as a whole word."""
    lowered = text.lower()
    return [brand for brand, pattern in _BRAND_ALIAS_RES if pattern.search(lowered)]


def claimed_brands(company_name: str | None, text: str) -> list[Brand]:
    """Known brands the letter claims to come from.

    Prefers Gemini's `company_name`. Without it, scans the text but first
    removes product mentions ("Google Meet", "Amazon Pay") so a genuine letter
    that schedules a Teams call is not treated as claiming to be Microsoft.
    """
    if company_name:
        return brands_mentioned(company_name)
    return brands_mentioned(_PRODUCT_MENTION_RE.sub(" ", text))


def _name_matches_domain(company: str, domain: str) -> bool:
    """Loose match between a company name and a domain label.

    True if a significant word of the name (or its acronym) appears in the
    label, e.g. "Nexora Analytics Pvt Ltd" ~ nexora.in, "Tata Consultancy
    Services" ~ tcs.com.
    """
    label = _label(domain).replace("-", "")
    words = [w for w in re.findall(r"[a-z0-9]+", company.lower()) if w not in COMPANY_STOPWORDS]
    if any(len(w) >= 3 and w in label for w in words):
        return True
    all_words = re.findall(r"[a-z0-9]+", company.lower())
    acronym = "".join(w[0] for w in all_words if w not in {"pvt", "ltd", "private", "limited"})
    return len(acronym) >= 2 and acronym in label


def find_company_domain_mismatch(
    company_name: str | None, text: str, sender_emails: list[str]
) -> list[str]:
    """Sender domains that don't belong to the company the letter claims to be from.

    Known brands the letter claims to be from are checked against their
    official domains; any other company name (from Gemini) is matched loosely.
    """
    sender_domains = list(dict.fromkeys(
        registrable_domain(email_domain(e)) or email_domain(e) for e in sender_emails
    ))
    if not sender_domains:
        return []
    hits: list[str] = []
    brands = claimed_brands(company_name, text)
    for brand in brands:
        if not any(is_official_domain(d, brand) for d in sender_domains):
            hits.append(
                f"Letter mentions {brand.name} but emails come from {', '.join(sender_domains)}"
            )
    if company_name and not brands and not any(_name_matches_domain(company_name, d) for d in sender_domains):
        hits.append(f"Company '{company_name}' does not match sender domain(s) {', '.join(sender_domains)}")
    return hits


def find_suspicious_tlds(domains: list[str]) -> list[str]:
    """Domains on TLDs heavily abused for phishing."""
    return [f"{d} (.{tld_of(d)})" for d in domains if tld_of(d) in SUSPICIOUS_TLDS]


def find_shorteners(urls: list[str]) -> list[str]:
    """URLs that go through a link shortener."""
    return [u for u in urls if (host_of(u) or "") in URL_SHORTENERS]


def find_insecure_urls(urls: list[str]) -> list[str]:
    """URLs explicitly using plain ``http://``."""
    return [u for u in urls if u.lower().startswith("http://")]
