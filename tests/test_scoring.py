"""Unit tests for the deterministic scoring engine (no I/O, no mocks needed)."""

import pytest

from app.models import RiskBand, ScanFacts, SkippedCheck
from app.scoring import SIGNALS, risk_band, score_scan

OBVIOUS_SCAM = ScanFacts(
    payment_demand_evidence=["Pay Rs. 4,999 refundable registration fee"],
    untraceable_payment_evidence=["UPI ID tcshr.recruit@ybl"],
    sensitive_document_evidence=["Send Aadhaar card and PAN card copy"],
    urgency_phrases=["within 24 hours", "offer will be cancelled"],
    interview_mentioned=False,
    unrealistic_salary=True,
    salary_evidence="Rs. 85,000/month for a fresher data entry role",
    poor_grammar=True,
    free_email_senders=["hr.tcs.recruitment@gmail.com"],
    company_domain_mismatch=["TCS vs gmail.com"],
    lookalike_domains=["tcs-careers.xyz resembles tcs.com"],
    suspicious_tld_domains=["tcs-careers.xyz"],
    domain_ages={"tcs-careers.xyz": 9},
)

SUBTLE_SCAM = ScanFacts(
    payment_demand_evidence=["refundable security deposit of INR 7,500 for laptop"],
    sensitive_document_evidence=["bank account details for salary setup"],
    urgency_phrases=["confirm by Friday"],
    interview_mentioned=True,
    unrealistic_salary=False,
    poor_grammar=False,
    company_domain_mismatch=["Nexora Analytics vs nexora-hr.co"],
    domain_ages={"nexora-hr.co": 95},
)

LEGITIMATE = ScanFacts(
    interview_mentioned=True,
    unrealistic_salary=False,
    poor_grammar=False,
    domain_ages={"infosys.com": 10_500},
)


def _ids(facts: ScanFacts) -> set[str]:
    return {hit.id for hit in score_scan(facts).breakdown}


def test_obvious_scam_scores_high() -> None:
    result = score_scan(OBVIOUS_SCAM)
    assert result.score >= 70
    assert result.band is RiskBand.HIGH


def test_subtle_scam_is_not_low() -> None:
    result = score_scan(SUBTLE_SCAM)
    assert result.score >= 30
    assert result.band is not RiskBand.LOW


def test_legitimate_offer_scores_low() -> None:
    result = score_scan(LEGITIMATE)
    assert result.score <= 25
    assert result.band is RiskBand.LOW
    assert result.breakdown == []


def test_scoring_is_deterministic() -> None:
    assert score_scan(OBVIOUS_SCAM) == score_scan(OBVIOUS_SCAM.model_copy(deep=True))


def test_score_is_capped_and_raw_total_is_kept() -> None:
    result = score_scan(OBVIOUS_SCAM)
    assert result.score == 100
    assert result.raw_total > 100


def test_score_equals_sum_of_breakdown_when_uncapped() -> None:
    result = score_scan(SUBTLE_SCAM)
    assert result.score == sum(hit.points for hit in result.breakdown)
    # payment 30 + young domain 12 + sensitive docs 15 + mismatch 10 + urgency 5
    assert result.score == 72


def test_empty_facts_score_zero() -> None:
    result = score_scan(ScanFacts())
    assert result.score == 0
    assert result.band is RiskBand.LOW


@pytest.mark.parametrize(
    ("score", "band"),
    [(0, RiskBand.LOW), (29, RiskBand.LOW), (30, RiskBand.SUSPICIOUS),
     (59, RiskBand.SUSPICIOUS), (60, RiskBand.HIGH), (100, RiskBand.HIGH)],
)
def test_risk_band_boundaries(score: int, band: RiskBand) -> None:
    assert risk_band(score) is band


def test_free_email_suppresses_domain_mismatch() -> None:
    facts = ScanFacts(free_email_senders=["a@gmail.com"], company_domain_mismatch=["X"])
    assert _ids(facts) == {"free_email"}


def test_domain_mismatch_counts_without_free_email() -> None:
    assert _ids(ScanFacts(company_domain_mismatch=["X"])) == {"domain_mismatch"}


def test_new_domain_suppresses_young_domain() -> None:
    facts = ScanFacts(domain_ages={"a.xyz": 5, "b.in": 100})
    assert _ids(facts) == {"new_domain"}


@pytest.mark.parametrize(
    ("age", "expected"),
    [(0, {"new_domain"}), (29, {"new_domain"}), (30, {"young_domain"}),
     (179, {"young_domain"}), (180, set()), (5000, set())],
)
def test_domain_age_tiers(age: int, expected: set[str]) -> None:
    assert _ids(ScanFacts(domain_ages={"example.com": age})) == expected


@pytest.mark.parametrize(("count", "points"), [(1, 5), (2, 10), (5, 10)])
def test_urgency_points_scale_per_phrase_with_cap(count: int, points: int) -> None:
    facts = ScanFacts(urgency_phrases=[f"phrase {i}" for i in range(count)])
    assert score_scan(facts).score == points


def test_duplicate_evidence_is_counted_once() -> None:
    facts = ScanFacts(urgency_phrases=["act now", "act now", ""])
    result = score_scan(facts)
    assert result.score == 5
    assert result.breakdown[0].evidence == ["act now"]


def test_unknown_llm_facts_do_not_fire() -> None:
    """None means Gemini was skipped: absence of data must not add points."""
    facts = ScanFacts(interview_mentioned=None, unrealistic_salary=None, poor_grammar=None)
    assert score_scan(facts).score == 0


def test_no_interview_fires_only_on_explicit_false() -> None:
    assert _ids(ScanFacts(interview_mentioned=False)) == {"no_interview"}
    assert _ids(ScanFacts(interview_mentioned=True)) == set()


def test_skipped_checks_are_passed_through() -> None:
    skipped = [SkippedCheck(check="Gemini extraction", reason="GEMINI_API_KEY not set")]
    result = score_scan(ScanFacts(skipped_checks=skipped))
    assert result.skipped_checks == skipped


def test_breakdown_sorted_by_points_and_explained() -> None:
    breakdown = score_scan(OBVIOUS_SCAM).breakdown
    points = [hit.points for hit in breakdown]
    assert points == sorted(points, reverse=True)
    assert all(hit.explanation and hit.evidence for hit in breakdown)


def test_signal_table_is_well_formed() -> None:
    ids = [signal.id for signal in SIGNALS]
    assert len(ids) == len(set(ids))
    assert all(signal.points > 0 for signal in SIGNALS)
    assert all(signal.suppressed_by in ids for signal in SIGNALS if signal.suppressed_by)
