"""Test doubles for Gemini (no network, no SDK calls)."""

import asyncio
from types import SimpleNamespace
from typing import Any

from app.extractor import ExtractedOffer, GeminiExtractor


class FakeModels:
    """Mimics `client.aio.models` and records calls."""

    def __init__(
        self,
        response_text: str | None = None,
        error: Exception | None = None,
        delay: float = 0,
        errors_by_model: dict[str, Exception] | None = None,
    ) -> None:
        self.response_text = response_text
        self.error = error
        self.delay = delay
        self.errors_by_model = errors_by_model or {}
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        if kwargs.get("model") in self.errors_by_model:
            raise self.errors_by_model[kwargs["model"]]
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.response_text)


class FakeClient:
    """Mimics `genai.Client` just enough for `GeminiExtractor`."""

    def __init__(self, models: FakeModels) -> None:
        self.aio = SimpleNamespace(models=models)


def make_extraction(**overrides: Any) -> ExtractedOffer:
    """A benign extraction; override fields per test."""
    base: dict[str, Any] = {
        "company_name": None, "sender_emails": [], "domains": [],
        "payment_demanded": False, "payment_amount": None, "payment_purpose": "none",
        "payment_method": "none", "payment_quotes": [], "urgency_phrases": [],
        "interview_mentioned": True, "salary_mentioned": False, "unrealistic_salary": False,
        "salary_quote": None, "requests_sensitive_documents": False,
        "sensitive_document_quotes": [], "grammar_quality": "good", "suspicious_quotes": [],
    }
    return ExtractedOffer.model_validate(base | overrides)


def fake_extractor(
    extraction: ExtractedOffer | None = None, fallback_model: str | None = None, **model_kwargs: Any
) -> tuple[GeminiExtractor, FakeModels]:
    """An extractor whose client returns `extraction` as JSON."""
    if extraction is not None:
        model_kwargs.setdefault("response_text", extraction.model_dump_json())
    models = FakeModels(**model_kwargs)
    extractor = GeminiExtractor(
        api_key=None, model="test-model", timeout_seconds=1, client=FakeClient(models), fallback_model=fallback_model
    )
    return extractor, models
