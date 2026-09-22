"""Manual smoke test: run live Gemini extraction + scoring on a built-in sample.

Usage (needs GEMINI_API_KEY in the environment; makes real API calls):
    python -m scripts.try_extraction subtle_scam
"""

import asyncio
import sys

import httpx

from app.config import Settings
from app.extractor import GeminiExtractor
from app.pipeline import run_scan
from app.samples import SAMPLES, get_sample


async def main(sample_id: str) -> None:
    """Scan one sample and print Gemini's facts and the scored report."""
    settings = Settings.from_env()
    extractor = GeminiExtractor(
        settings.gemini_api_key, settings.gemini_model, settings.gemini_timeout_seconds,
        fallback_model=settings.gemini_fallback_model,
    )
    text = get_sample(sample_id).text
    extracted, skipped = await extractor.extract(text)
    print("--- Gemini extraction ---")
    print(extracted.model_dump_json(indent=2) if extracted else skipped)
    async with httpx.AsyncClient() as client:
        report = await run_scan(text, None, extractor, client, settings.safe_browsing_api_key)
    print("--- Report ---")
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else "subtle_scam"
    if choice not in {s.id for s in SAMPLES}:
        sys.exit(f"Unknown sample. Choose one of: {', '.join(s.id for s in SAMPLES)}")
    asyncio.run(main(choice))
