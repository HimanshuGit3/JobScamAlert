"""HTTP-level tests of the FastAPI app (Gemini and outbound HTTP are faked)."""

import re
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import MAX_TEXT_CHARS, MAX_URL_CHARS
from app.samples import SAMPLES, get_sample
from tests.fakes import fake_extractor, make_extraction

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_SOURCES = sorted((FRONTEND / "src").rglob("*.ts*"))

SETTINGS = Settings(gemini_api_key=None, gemini_model="test-model",
                    gemini_timeout_seconds=1, safe_browsing_api_key=None,
                    rate_limit_per_minute=1000)


async def _fake_page(url: str) -> str:
    return "Pay the registration fee of Rs. 500 now."


def _outbound(request: httpx.Request) -> httpx.Response:
    if request.url.host == "rdap.org":
        return httpx.Response(404)
    return httpx.Response(200, json={})


@pytest.fixture
def client(static_dir: Path) -> Iterator[TestClient]:
    extractor, _ = fake_extractor(make_extraction(company_name="Infosys Limited"))
    http = httpx.AsyncClient(transport=httpx.MockTransport(_outbound))
    app = create_app(SETTINGS, extractor=extractor, http_client=http, page_fetcher=_fake_page,
                     static_dir=static_dir)
    with TestClient(app) as test_client:
        yield test_client


def test_index_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert '<div id="root">' in response.text


def test_built_assets_served(client: TestClient) -> None:
    for path in ("/assets/app.js", "/favicon.svg"):
        assert client.get(path).status_code == 200
    assert client.get("/assets/missing.js").status_code == 404


def test_unbuilt_frontend_returns_helpful_503(tmp_path: Path) -> None:
    extractor, _ = fake_extractor(make_extraction())
    with TestClient(create_app(SETTINGS, extractor=extractor, static_dir=tmp_path)) as test_client:
        response = test_client.get("/")
        assert response.status_code == 503
        assert "npm run build" in response.text
        assert test_client.get("/healthz").status_code == 200  # API still works


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_status_never_exposes_keys(client: TestClient) -> None:
    body = client.get("/api/status").json()
    assert body == {"gemini": True, "safe_browsing": False, "model": "test-model",
                    "fetch_linked_pages": True}


def test_samples_endpoint(client: TestClient) -> None:
    body = client.get("/api/samples").json()
    assert [s["id"] for s in body] == [s.id for s in SAMPLES]


def test_scan_scam_sample(client: TestClient) -> None:
    response = client.post("/api/scan", json={"text": get_sample("obvious_scam").text})
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["score"] >= 70
    assert body["result"]["band"] == "High Risk"
    assert body["highlights"]
    assert all({"signal", "points", "evidence", "explanation"} <= hit.keys()
               for hit in body["result"]["breakdown"])


def test_scan_legitimate_sample(client: TestClient) -> None:
    body = client.post("/api/scan", json={"text": get_sample("legitimate").text}).json()
    assert body["result"]["score"] <= 25


def test_scan_url_only_analyses_linked_page(client: TestClient) -> None:
    body = client.post("/api/scan", json={"url": "http://bit.ly/abc"}).json()
    ids = {h["id"] for h in body["result"]["breakdown"]}
    assert {"url_shortener", "payment_demand"} <= ids  # payment came from the fetched page
    assert "Pay the registration fee of Rs. 500 now." in body["analyzed_text"]
    assert body["highlights"] == ["Pay the registration fee of Rs. 500 now."]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"text": "   ", "url": ""},
        {"text": "x" * (MAX_TEXT_CHARS + 1)},
        {"url": "https://a.com/" + "x" * MAX_URL_CHARS},
        {"url": "javascript:alert(1)"},
        {"url": "file:///etc/passwd"},
        {"url": "ftp://example.com"},
        {"text": "hi", "unexpected": 1},
    ],
)
def test_scan_rejects_invalid_input(client: TestClient, payload: dict) -> None:
    assert client.post("/api/scan", json=payload).status_code == 422


def test_frontend_sources_exist() -> None:
    assert FRONTEND_SOURCES, "frontend/src not found"


@pytest.mark.parametrize("source", FRONTEND_SOURCES, ids=lambda p: p.name)
def test_frontend_never_injects_raw_html(source: Path) -> None:
    """React escapes text by default; these APIs are the ways around it."""
    code = source.read_text(encoding="utf-8")
    assert not re.search(r"dangerouslySetInnerHTML|\.(innerHTML|outerHTML)\b|insertAdjacentHTML|document\.write", code)


def test_frontend_limits_match_backend() -> None:
    config = (FRONTEND / "src" / "config.ts").read_text(encoding="utf-8")
    assert f"MAX_TEXT_CHARS = {MAX_TEXT_CHARS};" in config
    assert f"MAX_URL_CHARS = {MAX_URL_CHARS};" in config


def test_html_shell_has_no_inline_scripts_or_handlers() -> None:
    """Keeps the page compatible with a strict CSP (no 'unsafe-inline')."""
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert not re.search(r"\son[a-z]+=", html)
    assert "style=" not in html
