"""Regex-based parsing of offer text.

This is the deterministic backup to Gemini: URLs, emails, payment demands,
untraceable payment methods, sensitive-document requests and urgency phrases.
All evidence returned is an exact substring of the input so the UI can
highlight it.
"""

import re

from app.checks.data import BARE_DOMAIN_TLDS

MAX_ITEMS = 20
MAX_EVIDENCE_CHARS = 300

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}")
_URL_RE = re.compile(r"\bhttps?://[^\s<>\"'`{}|\\^]+", re.IGNORECASE)
_BARE_DOMAIN_RE = re.compile(
    r"(?<![@\w.-])(?:www\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+([a-z]{2,24})"
    r"(?:/[^\s<>\"'`]*)?(?![\w@-])",
    re.IGNORECASE,
)
_TRAILING_PUNCT = ".,;:!?)]}'\""
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])|\s*\n\s*")

_PAYMENT_FEE_RE = re.compile(
    r"\b(?:registration|processing|training|verification|onboarding|joining|"
    r"application|documentation|kit|uniform|laptop|equipment|interview|"
    r"background[- ]check|security|caution|refundable)\s+"
    r"(?:fee|fees|charges?|deposit|amount|money)\b"
    r"|\bsecurity\s+deposit\b|\bcaution\s+money\b|\brefundable\b",
    re.IGNORECASE,
)
# A payment verb followed, within a few words, by a money noun or currency amount.
# Bare numbers are not enough ("send your documents by 15 August").
_PAYMENT_ACTION_RE = re.compile(
    r"\b(?:pay|deposit|transfer|remit|send)\s+(?:[\w,.'-]+\s+){0,4}?"
    r"(?:amount|sum|fees?|charges?|deposit|advance|₹\s*\d|rs\.?\s*\d|inr\s*\d|rupees)",
    re.IGNORECASE,
)
_UPI_ID_RE = re.compile(
    r"\b[a-z0-9._-]{2,64}@(?:ybl|okaxis|oksbi|okhdfcbank|okicici|paytm|upi|apl|"
    r"ibl|axl|ptyes|ptsbi|ptaxis|pthdfc|icici|sbi|hdfcbank|axisbank|kotak|"
    r"yesbank|ikwik|fbl|freecharge|jio|airtel|axisb)(?![\w.-]*\.[a-z])\b",
    re.IGNORECASE,
)
_UNTRACEABLE_METHOD_RE = re.compile(
    r"\bgift\s*cards?\b|\b(?:google\s+play|amazon\s+pay|itunes)\s+(?:gift\s+)?(?:card|voucher)s?\b"
    r"|\b(?:bitcoin|btc|usdt|ethereum|crypto(?:currency)?)\b"
    r"|\b(?:via|through|using|on|to)\s+(?:upi|phonepe|gpay|google\s+pay|paytm)\b",
    re.IGNORECASE,
)
_SENSITIVE_DOC_RE = re.compile(
    r"\b(?:aadh?aar|pan\s+(?:card|number|no\.?)|bank\s+(?:account|details|statement)|"
    r"account\s+number|ifsc|passbook|cancell?ed\s+cheque|debit\s+card|credit\s+card|"
    r"passport)\b",
    re.IGNORECASE,
)
_ALWAYS_SENSITIVE_RE = re.compile(r"\b(?:otp|cvv|atm\s+pin|upi\s+pin|net\s*banking\s+password)\b", re.IGNORECASE)
_REQUEST_VERB_RE = re.compile(
    r"\b(?:send|share|submit|provide|upload|forward|whatsapp|e-?mail)\b", re.IGNORECASE
)
_AT_JOINING_RE = re.compile(
    r"\b(?:on|at the time of|during|upon)\s+(?:the\s+)?(?:day\s+of\s+)?(?:your\s+)?"
    r"(?:joining|first day|induction)\b",
    re.IGNORECASE,
)
_URGENCY_RE = re.compile(
    r"\bwithin\s+(?:\d{1,2}|twenty[- ]four|forty[- ]eight)\s*(?:hours?|hrs?)\b"
    r"|\b(?:urgent(?:ly)?|asap|today\s+itself|act\s+now|immediate\s+(?:payment|action))\b"
    r"|\blimited\s+(?:seats|slots|positions|vacancies)\b"
    r"|\bonly\s+\d+\s+(?:seats|slots|positions)\s+(?:left|remaining)\b"
    r"|\b(?:offer|seat|selection)\s+(?:will|shall)\s+be\s+(?:cancell?ed|withdrawn|revoked|forfeited)\b"
    r"|\bfailing\s+which\b",
    re.IGNORECASE,
)


def _dedupe(items: list[str], limit: int = MAX_ITEMS) -> list[str]:
    """Remove duplicates, keep order, cap length."""
    return list(dict.fromkeys(items))[:limit]


def _strip_trailing(value: str) -> str:
    """Remove punctuation that commonly trails a URL in prose."""
    return value.rstrip(_TRAILING_PUNCT)


def split_sentences(text: str) -> list[str]:
    """Split text into sentences; every returned item is a substring of `text`."""
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s and s.strip()]


def extract_emails(text: str) -> list[str]:
    """Return unique email addresses found in text (lower-cased)."""
    return _dedupe([m.group(0).lower() for m in _EMAIL_RE.finditer(text)])


def extract_urls(text: str) -> list[str]:
    """Return unique URLs, including bare domains like ``tcs-careers.xyz/apply``.

    Bare domains are only accepted with a known TLD (see ``BARE_DOMAIN_TLDS``)
    so that file names such as ``offer.pdf`` are not mistaken for sites.
    Email addresses are removed first so their domains are not double-counted.
    """
    urls = [_strip_trailing(m.group(0)) for m in _URL_RE.finditer(text)]
    remainder = _URL_RE.sub(" ", _EMAIL_RE.sub(" ", text))
    for match in _BARE_DOMAIN_RE.finditer(remainder):
        if match.group(1).lower() in BARE_DOMAIN_TLDS:
            urls.append(_strip_trailing(match.group(0)))
    return _dedupe(urls)


def _matching_sentences(text: str, *patterns: re.Pattern[str]) -> list[str]:
    """Sentences matching any of `patterns`, truncated for display."""
    return _dedupe([
        s[:MAX_EVIDENCE_CHARS]
        for s in split_sentences(text)
        if any(p.search(s) for p in patterns)
    ])


def detect_payment_demands(text: str) -> list[str]:
    """Sentences that ask the reader to pay a fee or deposit."""
    return _matching_sentences(text, _PAYMENT_FEE_RE, _PAYMENT_ACTION_RE)


def detect_untraceable_payment(text: str) -> list[str]:
    """Sentences mentioning UPI IDs, gift cards or crypto as payment."""
    return _matching_sentences(text, _UPI_ID_RE, _UNTRACEABLE_METHOD_RE)


def detect_sensitive_document_requests(text: str) -> list[str]:
    """Sentences requesting identity or banking documents before joining.

    A sentence counts when it names a sensitive document together with a
    request verb and does not say "at the time of joining". OTP/CVV/PIN
    requests always count: no employer legitimately needs them.
    """
    hits: list[str] = []
    for sentence in split_sentences(text):
        if _ALWAYS_SENSITIVE_RE.search(sentence) or (
            _SENSITIVE_DOC_RE.search(sentence)
            and _REQUEST_VERB_RE.search(sentence)
            and not _AT_JOINING_RE.search(sentence)
        ):
            hits.append(sentence[:MAX_EVIDENCE_CHARS])
    return _dedupe(hits)


def detect_urgency(text: str) -> list[str]:
    """Exact urgency phrases such as "within 24 hours" or "failing which"."""
    return _dedupe([m.group(0) for m in _URGENCY_RE.finditer(text)])
