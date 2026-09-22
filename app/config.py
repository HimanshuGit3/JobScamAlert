"""Runtime settings, read once from environment variables.

Secrets are never hard-coded; see `.env.example` for the full list.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
# Tried once if the primary model is overloaded/unavailable; "none" disables.
DEFAULT_GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"  # fast (~2s) and available when larger models are overloaded
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_local_env() -> None:
    """Load a git-ignored `.env` file for local development, if present.

    Real environment variables always win (`override=False`), so Cloud Run
    secrets are never replaced. The Docker image never contains `.env`.
    """
    if ENV_FILE.is_file():
        load_dotenv(ENV_FILE, override=False)


def _float_env(name: str, default: float) -> float:
    """Read a positive float from the environment, falling back on bad input."""
    try:
        value = float(os.environ.get(name, default))
    except ValueError:
        return default
    return value if value > 0 else default


def _int_env(name: str, default: int, minimum: int = 0) -> int:
    """Read an integer >= minimum from the environment, falling back on bad input."""
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        return default
    return value if value >= minimum else default


def _bool_env(name: str, default: bool) -> bool:
    """Read a boolean flag ("true"/"false", "1"/"0")."""
    raw = os.environ.get(name, "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _fallback_model() -> str | None:
    """GEMINI_FALLBACK_MODEL, defaulting to a stable Flash model; "none" disables it."""
    value = os.environ.get("GEMINI_FALLBACK_MODEL", DEFAULT_GEMINI_FALLBACK_MODEL).strip()
    return None if value.lower() in {"", "none", "off"} else value


def _secret_env(name: str) -> str | None:
    """Read a secret; empty strings count as missing."""
    value = os.environ.get(name, "").strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    """Application settings."""

    gemini_api_key: str | None
    gemini_model: str
    gemini_timeout_seconds: float
    safe_browsing_api_key: str | None
    gemini_fallback_model: str | None = None
    rate_limit_per_minute: int = 10
    trusted_proxy_count: int = 0
    fetch_linked_pages: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from the environment (plus `.env` in local development)."""
        load_local_env()
        return cls(
            gemini_api_key=_secret_env("GEMINI_API_KEY"),
            gemini_model=os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL,
            gemini_timeout_seconds=_float_env("GEMINI_TIMEOUT_SECONDS", 20.0),
            safe_browsing_api_key=_secret_env("SAFE_BROWSING_API_KEY"),
            gemini_fallback_model=_fallback_model(),
            rate_limit_per_minute=_int_env("RATE_LIMIT_PER_MINUTE", 10, minimum=1),
            trusted_proxy_count=_int_env("TRUSTED_PROXY_COUNT", 0),
            fetch_linked_pages=_bool_env("FETCH_LINKED_PAGES", True),
        )
