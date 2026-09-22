"""Deterministic Scam Threat Index scoring engine.

Design rule: the LLM *extracts facts*, this module *scores* them. Nothing here
calls a network or a model, so the same `ScanFacts` always yields the same
score, and every point in the score is traceable to one row of `SIGNALS`.

Score = sum of points of every signal that fired, capped at 100.
Bands: 0-29 Low, 30-59 Suspicious, 60-100 High Risk.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.models import RiskBand, ScanFacts, ScoreResult, SignalHit

MAX_SCORE = 100
SUSPICIOUS_THRESHOLD = 30
HIGH_RISK_THRESHOLD = 60
NEW_DOMAIN_DAYS = 30
YOUNG_DOMAIN_DAYS = 180
MAX_EVIDENCE_ITEMS = 5

Evaluator = Callable[[ScanFacts], list[str]]


@dataclass(frozen=True)
class Signal:
    """One weighted scoring rule.

    Attributes:
        id: Stable machine identifier.
        label: Human-readable name shown in the UI.
        points: Points awarded when the signal fires (or per item, see below).
        explanation: Why this signal indicates a scam.
        evaluate: Returns evidence strings; an empty list means "not fired".
        max_points: If set, `points` is awarded per evidence item, capped here.
        suppressed_by: Id of a stronger, overlapping signal. If that one
            fires, this one is dropped so the same fact is not counted twice.
    """

    id: str
    label: str
    points: int
    explanation: str
    evaluate: Evaluator
    max_points: int | None = None
    suppressed_by: str | None = None


def _field(name: str) -> Evaluator:
    """Build an evaluator that returns a list-typed `ScanFacts` field."""
    return lambda facts: list(getattr(facts, name))


def _domains_by_age(min_days: int, max_days: int) -> Evaluator:
    """Build an evaluator for domains aged within [min_days, max_days)."""

    def evaluate(facts: ScanFacts) -> list[str]:
        return [
            f"{domain} was registered {age} days ago"
            for domain, age in sorted(facts.domain_ages.items())
            if min_days <= age < max_days
        ]

    return evaluate


def _no_interview(facts: ScanFacts) -> list[str]:
    """Fires only when Gemini positively found no interview (not when unknown)."""
    if facts.interview_mentioned is False:
        return ["No interview, test or selection round is mentioned"]
    return []


def _unrealistic_salary(facts: ScanFacts) -> list[str]:
    """Fires when Gemini judged the salary unrealistic for the role."""
    if facts.unrealistic_salary:
        return [facts.salary_evidence or "Salary is unusually high for the role"]
    return []


def _poor_grammar(facts: ScanFacts) -> list[str]:
    """Fires when Gemini rated the writing quality as poor."""
    if facts.poor_grammar:
        return ["Spelling, grammar or formatting is poor for an official letter"]
    return []


# The single source of truth for weights. Edit here; tests and README follow.
SIGNALS: tuple[Signal, ...] = (
    Signal(
        "safe_browsing", "Flagged by Google Safe Browsing", 40,
        "Google lists this URL as phishing, malware or unwanted software.",
        _field("safe_browsing_matches"),
    ),
    Signal(
        "payment_demand", "Asks you to pay money", 30,
        "Genuine employers and landlords' agents never charge a fee to "
        "hire you; registration, training, equipment or 'refundable' "
        "deposits are the core of this scam.",
        _field("payment_demand_evidence"),
    ),
    Signal(
        "new_domain", "Domain registered in the last 30 days", 25,
        "Scam sites are created days before a campaign; real employers "
        "use domains that are years old.",
        _domains_by_age(0, NEW_DOMAIN_DAYS),
    ),
    Signal(
        "young_domain", "Domain registered in the last 6 months", 12,
        "A recently registered domain is unusual for an established employer.",
        _domains_by_age(NEW_DOMAIN_DAYS, YOUNG_DOMAIN_DAYS),
        suppressed_by="new_domain",
    ),
    Signal(
        "lookalike_domain", "Imitates a well-known employer's domain", 25,
        "Typosquatted or hyphenated look-alike domains borrow a real "
        "brand's trust.",
        _field("lookalike_domains"),
    ),
    Signal(
        "free_email", "Corporate offer sent from a free email account", 15,
        "Real companies send offers from their own domain, not Gmail, "
        "Yahoo or Outlook.",
        _field("free_email_senders"),
    ),
    Signal(
        "sensitive_documents", "Asks for Aadhaar, PAN or bank details early", 15,
        "Identity and bank documents requested before joining enable "
        "identity theft and fraud.",
        _field("sensitive_document_evidence"),
    ),
    Signal(
        "untraceable_payment", "Untraceable payment method", 10,
        "UPI to a personal ID, gift cards and crypto are hard to reverse "
        "and are favoured by fraudsters.",
        _field("untraceable_payment_evidence"),
    ),
    Signal(
        "domain_mismatch", "Company name does not match sender domain", 10,
        "The sender's domain does not belong to the company named in the "
        "letter.",
        _field("company_domain_mismatch"),
        suppressed_by="free_email",
    ),
    Signal(
        "no_interview", "Offer without any interview", 10,
        "Legitimate jobs involve a selection process; instant offers are "
        "bait.",
        _no_interview,
    ),
    Signal(
        "unrealistic_salary", "Unrealistic salary", 10,
        "Pay far above market rate for the role is used to lower your guard.",
        _unrealistic_salary,
    ),
    Signal(
        "suspicious_tld", "Suspicious top-level domain", 10,
        "Cheap TLDs such as .xyz or .top are heavily abused for phishing.",
        _field("suspicious_tld_domains"),
    ),
    Signal(
        "urgency", "Pressure to act immediately", 5,
        "Artificial deadlines stop you from verifying the offer.",
        _field("urgency_phrases"),
        max_points=10,
    ),
    Signal(
        "url_shortener", "Link hidden behind a URL shortener", 8,
        "Shorteners hide the real destination of a link.",
        _field("shortener_urls"),
    ),
    Signal(
        "insecure_url", "Link does not use HTTPS", 5,
        "Official career portals use HTTPS.",
        _field("insecure_urls"),
    ),
    Signal(
        "poor_grammar", "Poor grammar or formatting", 5,
        "Official HR letters are proofread; sloppy writing is a weak "
        "scam indicator.",
        _poor_grammar,
    ),
)


def risk_band(score: int) -> RiskBand:
    """Map a 0-100 score to its risk band."""
    if score >= HIGH_RISK_THRESHOLD:
        return RiskBand.HIGH
    if score >= SUSPICIOUS_THRESHOLD:
        return RiskBand.SUSPICIOUS
    return RiskBand.LOW


def _signal_points(signal: Signal, evidence_count: int) -> int:
    """Points for a fired signal, scaling per item when `max_points` is set."""
    if signal.max_points is None:
        return signal.points
    return min(signal.points * evidence_count, signal.max_points)


def score_scan(facts: ScanFacts) -> ScoreResult:
    """Compute the Scam Threat Index from merged facts.

    Pure function: no I/O, no randomness, no model calls.
    """
    evidence_by_id: dict[str, list[str]] = {}
    for signal in SIGNALS:
        # De-duplicate while preserving order so output is stable.
        evidence = list(dict.fromkeys(e for e in signal.evaluate(facts) if e))
        if evidence:
            evidence_by_id[signal.id] = evidence

    breakdown: list[SignalHit] = []
    for signal in SIGNALS:
        fired = evidence_by_id.get(signal.id)
        if not fired or signal.suppressed_by in evidence_by_id:
            continue
        breakdown.append(
            SignalHit(
                id=signal.id,
                signal=signal.label,
                points=_signal_points(signal, len(fired)),
                evidence=fired[:MAX_EVIDENCE_ITEMS],
                explanation=signal.explanation,
            )
        )

    breakdown.sort(key=lambda hit: hit.points, reverse=True)  # stable sort
    raw_total = sum(hit.points for hit in breakdown)
    score = min(raw_total, MAX_SCORE)
    return ScoreResult(
        score=score,
        band=risk_band(score),
        raw_total=raw_total,
        breakdown=breakdown,
        skipped_checks=list(facts.skipped_checks),
    )
