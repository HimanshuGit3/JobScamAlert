"""Tests for offline domain heuristics: typosquats, free email, mismatch, TLDs."""

import pytest

from app.checks import domains as dom


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("careers.tcs.com", "tcs.com"),
        ("hr.nexora.co.in", "nexora.co.in"),
        ("tcs-careers.xyz", "tcs-careers.xyz"),
        ("192.168.1.1", None),
        ("localhost", None),
    ],
)
def test_registrable_domain(host: str, expected: str | None) -> None:
    assert dom.registrable_domain(host) == expected


def test_host_of_accepts_bare_domains() -> None:
    assert dom.host_of("Tcs-Careers.XYZ/join") == "tcs-careers.xyz"
    assert dom.host_of("https://a.b.com:8443/x") == "a.b.com"


@pytest.mark.parametrize(("a", "b", "distance"), [("kitten", "sitting", 3), ("", "abc", 3), ("same", "same", 0)])
def test_levenshtein(a: str, b: str, distance: int) -> None:
    assert dom.levenshtein(a, b) == distance


@pytest.mark.parametrize(
    "domain",
    [
        "tcs-careers.xyz",      # brand as hyphenated part
        "infosyscareers.in",    # long brand embedded
        "inf0sys.com",          # homoglyph
        "infosis.com",          # edit distance 1
        "accentrue.com",        # transposition
        "careers-wipro.online",
        "amazon-jobs.co.in",
    ],
)
def test_lookalike_domains_detected(domain: str) -> None:
    assert len(dom.find_lookalike_domains([domain])) == 1


@pytest.mark.parametrize(
    "domain",
    ["tcs.com", "infosys.com", "amazon.in", "nexora.in", "gmail.com", "stcsolutions.com", "metals.com"],
)
def test_official_and_unrelated_domains_not_flagged(domain: str) -> None:
    assert dom.find_lookalike_domains([domain]) == []


def test_free_email_senders() -> None:
    hits = dom.find_free_email_senders(["hr.tcs@gmail.com", "hr@infosys.com", "x@yahoo.co.in"])
    assert [h.split()[0] for h in hits] == ["hr.tcs@gmail.com", "x@yahoo.co.in"]


def test_mismatch_known_brand_from_other_domain() -> None:
    hits = dom.find_company_domain_mismatch(None, "Offer from Infosys Limited", ["hr@infosys-hr.in"])
    assert len(hits) == 1 and "Infosys" in hits[0]


def test_no_mismatch_for_official_brand_domain() -> None:
    assert dom.find_company_domain_mismatch(None, "Offer from Infosys", ["hr@careers.infosys.com"]) == []


def test_product_mentions_are_not_claimed_brands() -> None:
    text = "Nexora Analytics invites you to an interview on Google Meet and Microsoft Teams."
    assert dom.find_company_domain_mismatch(None, text, ["hr@nexora.in"]) == []


@pytest.mark.parametrize(
    ("company", "email", "mismatch"),
    [
        ("Nexora Analytics Pvt Ltd", "hr@nexora.in", False),
        ("Tata Consultancy Services", "hr@tcs.com", False),
        ("Blue Ocean Logistics", "hr@bol-hiring.com", False),  # acronym
        ("Nexora Analytics", "hr@quickjobs-hr.com", True),
    ],
)
def test_company_name_matching(company: str, email: str, mismatch: bool) -> None:
    assert bool(dom.find_company_domain_mismatch(company, "", [email])) is mismatch


def test_no_senders_no_mismatch() -> None:
    assert dom.find_company_domain_mismatch("Acme", "Acme", []) == []


def test_suspicious_tld_shortener_and_insecure() -> None:
    assert dom.find_suspicious_tlds(["a.xyz", "b.com"]) == ["a.xyz (.xyz)"]
    assert dom.find_shorteners(["https://bit.ly/x", "https://b.com"]) == ["https://bit.ly/x"]
    assert dom.find_insecure_urls(["http://a.com", "https://b.com", "c.com"]) == ["http://a.com"]
