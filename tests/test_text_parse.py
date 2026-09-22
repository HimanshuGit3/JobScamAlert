"""Tests for regex-based text parsing (the deterministic backup to Gemini)."""

import pytest

from app.checks import text_parse as tp


def test_extract_emails_lowercases_and_dedupes() -> None:
    text = "Mail HR@Example.com or hr@example.com, cc boss@corp.co.in."
    assert tp.extract_emails(text) == ["hr@example.com", "boss@corp.co.in"]


def test_extract_urls_full_and_bare_without_trailing_punctuation() -> None:
    text = "Apply at https://jobs.example.com/apply?id=7. Or visit tcs-careers.xyz/join, now!"
    assert tp.extract_urls(text) == ["https://jobs.example.com/apply?id=7", "tcs-careers.xyz/join"]


def test_extract_urls_ignores_email_domains_and_file_names() -> None:
    text = "Write to hr@company.com and open offer.pdf and Annexure.docx"
    assert tp.extract_urls(text) == []


@pytest.mark.parametrize(
    "sentence",
    [
        "Pay a registration fee of Rs. 2,000 to confirm.",
        "Please transfer a refundable security deposit of INR 7,500.",
        "Kindly pay the token advance of ₹10,000 today.",
        "A laptop charges of 3500 is applicable.",
        "The amount is fully refundable after training.",
    ],
)
def test_payment_demands_detected(sentence: str) -> None:
    assert tp.detect_payment_demands(sentence) == [sentence]


@pytest.mark.parametrize(
    "sentence",
    [
        "Your salary will be Rs. 30,000 per month.",
        "Pay: Rs 30,000 per month.",
        "Please send your documents by 15 August.",
        "We never charge candidates any fee.",
    ],
)
def test_payment_regex_ignores_salary_and_dates(sentence: str) -> None:
    assert tp.detect_payment_demands(sentence) == []


def test_currency_abbreviation_does_not_split_sentence() -> None:
    assert tp.split_sentences("Pay Rs. 4,999 now. Thanks") == ["Pay Rs. 4,999 now.", "Thanks"]


@pytest.mark.parametrize(
    "sentence",
    [
        "Send the amount to hrdesk@ybl.",
        "Pay using Google Play gift cards.",
        "Transfer the fee in USDT.",
        "Pay through PhonePe to confirm.",
    ],
)
def test_untraceable_payment_detected(sentence: str) -> None:
    assert tp.detect_untraceable_payment(sentence) == [sentence]


def test_upi_regex_does_not_match_normal_email() -> None:
    assert tp.detect_untraceable_payment("Contact hr@paytm.com for details.") == []


def test_sensitive_documents_requested_before_joining() -> None:
    text = "Kindly send your Aadhaar card and PAN card on WhatsApp."
    assert tp.detect_sensitive_document_requests(text) == [text]


def test_sensitive_documents_at_joining_are_fine() -> None:
    text = "Please submit copies of your PAN card at the time of joining."
    assert tp.detect_sensitive_document_requests(text) == []


def test_otp_request_always_flagged() -> None:
    text = "Tell us the OTP you receive to complete verification."
    assert tp.detect_sensitive_document_requests(text) == [text]


def test_urgency_phrases_are_exact_substrings() -> None:
    text = "Reply within 24 hours, failing which your offer will be cancelled."
    phrases = tp.detect_urgency(text)
    assert phrases == ["within 24 hours", "failing which", "offer will be cancelled"]
    assert all(p in text for p in phrases)


def test_normal_deadline_is_not_urgency() -> None:
    assert tp.detect_urgency("Please accept this offer within 7 days.") == []


def test_extraction_is_capped() -> None:
    text = " ".join(f"user{i}@example.com" for i in range(100))
    assert len(tp.extract_emails(text)) == tp.MAX_ITEMS
