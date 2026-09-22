"""Tests for security headers, body-size cap, rate limiting and no-logging of user content."""

import logging
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.middleware import RateLimiter, client_ip
from app.samples import get_sample
from tests.fakes import fake_extractor, make_extraction


def _app(static_dir: Path, rate_limit: int = 1000):
    settings = Settings(gemini_api_key=None, gemini_model="m", gemini_timeout_seconds=1,
                        safe_browsing_api_key=None, rate_limit_per_minute=rate_limit,
                        fetch_linked_pages=False)
    extractor, _ = fake_extractor(make_extraction())
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    return create_app(settings, extractor=extractor, http_client=http, static_dir=static_dir)


@pytest.fixture
def client(static_dir: Path):
    with TestClient(_app(static_dir)) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/", "/assets/app.js", "/api/status", "/healthz"])
def test_security_headers_present(client: TestClient, path: str) -> None:
    headers = client.get(path).headers
    csp = headers["content-security-policy"]
    assert "default-src 'none'" in csp and "script-src 'self'" in csp
    assert "unsafe-inline" not in csp and "frame-ancestors 'none'" in csp
    assert "font-src 'self'" in csp
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert "strict-transport-security" in headers


def test_api_responses_not_cached(client: TestClient) -> None:
    assert client.post("/api/scan", json={"text": "hello"}).headers["cache-control"] == "no-store"


def test_security_headers_on_error_responses(client: TestClient) -> None:
    response = client.post("/api/scan", json={})
    assert response.status_code == 422
    assert "content-security-policy" in response.headers


def test_validation_errors_do_not_echo_input(client: TestClient) -> None:
    secret = "MY-AADHAAR-1234-5678-9012"
    response = client.post("/api/scan", json={"text": "x" * 20_001 + secret})
    assert response.status_code == 422
    assert secret not in response.text
    assert "input" not in response.json()["detail"][0]


def test_oversized_body_rejected_with_413(client: TestClient) -> None:
    response = client.post("/api/scan", content=b"{" + b" " * 200_000 + b"}",
                           headers={"content-type": "application/json"})
    assert response.status_code == 413


def test_scan_endpoint_rate_limited(static_dir: Path) -> None:
    with TestClient(_app(static_dir, rate_limit=2)) as client:
        codes = [client.post("/api/scan", json={"text": "hi"}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]
        blocked = client.post("/api/scan", json={"text": "hi"})
        assert int(blocked.headers["retry-after"]) >= 1
        assert client.get("/api/samples").status_code == 200  # other endpoints unaffected


def test_rate_limiter_sliding_window() -> None:
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.check("a", now=0) is None
    assert limiter.check("a", now=1) is None
    assert limiter.check("a", now=2) == pytest.approx(58)
    assert limiter.check("b", now=2) is None       # separate key
    assert limiter.check("a", now=60.5) is None    # first hit expired


def test_rate_limiter_memory_is_bounded() -> None:
    limiter = RateLimiter(limit=1, window_seconds=60)
    limiter.MAX_TRACKED_KEYS = 100
    for i in range(1000):
        limiter.check(f"ip{i}", now=float(i))
    assert len(limiter._hits) <= 100


@pytest.mark.parametrize(
    ("peer", "xff", "trusted", "expected"),
    [
        ("1.1.1.1", "6.6.6.6", 0, "1.1.1.1"),                 # header ignored by default
        ("10.0.0.1", "6.6.6.6, 203.0.113.9", 1, "203.0.113.9"),  # spoofed left entry ignored
        ("10.0.0.1", "203.0.113.9, 10.0.0.2", 2, "203.0.113.9"),
        ("10.0.0.1", None, 1, "10.0.0.1"),
        (None, None, 0, "unknown"),
    ],
)
def test_client_ip(peer, xff, trusted, expected) -> None:
    assert client_ip(peer, xff, trusted) == expected


def test_user_text_never_logged(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    text = get_sample("obvious_scam").text
    assert client.post("/api/scan", json={"text": text}).status_code == 200
    logged = "\n".join(record.getMessage() for record in caplog.records)
    for fragment in ("tcshr.recruit@ybl", "Aadhaar", "tcs-careers.xyz", "hr.tcs.recruitment"):
        assert fragment not in logged
