"""Pydantic data models shared across the scanner.

`ScanFacts` is the single contract between fact-gathering (Gemini extraction +
deterministic checks) and the scoring engine. Every field is plain evidence:
a list of human-readable strings (empty = signal absent) or a tri-state bool
where ``None`` means "unknown because the check that produces it was skipped".
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_TEXT_CHARS = 20_000
MAX_URL_CHARS = 2_048


class ScanRequest(BaseModel):
    """Body of ``POST /api/scan``: pasted text, a URL, or both."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(default="", max_length=MAX_TEXT_CHARS)
    url: str | None = Field(default=None, max_length=MAX_URL_CHARS)

    @field_validator("url")
    @classmethod
    def _http_url_only(cls, value: str | None) -> str | None:
        """Accept only http(s) URLs; treat blank as absent."""
        if not value:
            return None
        if not value.lower().startswith(("http://", "https://")) or any(c.isspace() for c in value):
            raise ValueError("URL must start with http:// or https:// and contain no spaces")
        return value

    @model_validator(mode="after")
    def _needs_input(self) -> "ScanRequest":
        """Require at least one of text or URL."""
        if not self.text and not self.url:
            raise ValueError("Paste the offer text or enter a URL")
        return self


class RiskBand(StrEnum):
    """Risk band derived from the Scam Threat Index."""

    LOW = "Low"
    SUSPICIOUS = "Suspicious"
    HIGH = "High Risk"


class SkippedCheck(BaseModel):
    """A check that could not run (missing key, timeout, network error)."""

    check: str
    reason: str


class ScanFacts(BaseModel):
    """All facts the scoring engine needs, already merged from every source."""

    # Payment / document red flags (LLM and regex evidence merged).
    payment_demand_evidence: list[str] = Field(default_factory=list)
    untraceable_payment_evidence: list[str] = Field(default_factory=list)
    sensitive_document_evidence: list[str] = Field(default_factory=list)
    urgency_phrases: list[str] = Field(default_factory=list)

    # LLM-only judgements. None = Gemini extraction was skipped.
    interview_mentioned: bool | None = None
    unrealistic_salary: bool | None = None
    salary_evidence: str | None = None
    poor_grammar: bool | None = None

    # Deterministic sender / domain / URL checks.
    free_email_senders: list[str] = Field(default_factory=list)
    company_domain_mismatch: list[str] = Field(default_factory=list)
    lookalike_domains: list[str] = Field(default_factory=list)
    suspicious_tld_domains: list[str] = Field(default_factory=list)
    shortener_urls: list[str] = Field(default_factory=list)
    insecure_urls: list[str] = Field(default_factory=list)

    # External lookups.
    safe_browsing_matches: list[str] = Field(default_factory=list)
    domain_ages: dict[str, int] = Field(
        default_factory=dict, description="domain -> age in days (RDAP)"
    )

    skipped_checks: list[SkippedCheck] = Field(default_factory=list)


class SignalHit(BaseModel):
    """One scoring signal that fired, with its explanation."""

    id: str
    signal: str
    points: int
    evidence: list[str]
    explanation: str


class ScoreResult(BaseModel):
    """Final Scam Threat Index with a full, explainable breakdown."""

    score: int = Field(ge=0, le=100)
    band: RiskBand
    raw_total: int = Field(description="Sum of points before capping at 100")
    breakdown: list[SignalHit]
    skipped_checks: list[SkippedCheck]
