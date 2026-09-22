"""FastAPI application: JSON API plus the single static page."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.extractor import GeminiExtractor
from app.middleware import (
    BodySizeLimitMiddleware,
    RateLimiter,
    SecurityHeadersMiddleware,
    client_ip,
)
from app.models import ScanRequest
from app.pipeline import PageFetcher, ScanReport, run_scan
from app.samples import SAMPLES, Sample
from app.security import fetch_page_text

# Production build of the React UI (`npm run build` in frontend/).
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
NOT_BUILT_PAGE = (
    "<!DOCTYPE html><title>Frontend not built</title>"
    "<p>The UI has not been built. Run <code>npm ci &amp;&amp; npm run build</code> in <code>frontend/</code>. "
    "The API is available at <code>/api/scan</code>.</p>"
)
USER_AGENT = "OfferLetterInspector/1.0"
MAX_BODY_BYTES = 128 * 1024  # 20k chars of UTF-8 JSON fits comfortably

# Outbound request logs would contain domains taken from user letters.
# Keep them quiet: we never log user-submitted content.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def create_app(
    settings: Settings | None = None,
    extractor: GeminiExtractor | None = None,
    http_client: httpx.AsyncClient | None = None,
    page_fetcher: PageFetcher | None = None,
    static_dir: Path = FRONTEND_DIST,
) -> FastAPI:
    """Build the app. Tests inject fakes for Gemini, outbound HTTP, page fetching and the UI build."""
    settings = settings or Settings.from_env()
    if page_fetcher is None and settings.fetch_linked_pages:
        page_fetcher = fetch_page_text
    limiter = RateLimiter(settings.rate_limit_per_minute, window_seconds=60)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One pooled HTTP client for fixed third-party APIs (RDAP, Safe Browsing).
        # User-supplied URLs never use it; they go through the SSRF-safe fetcher.
        client = http_client or httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
        app.state.http = client
        app.state.extractor = extractor or GeminiExtractor(
            settings.gemini_api_key,
            settings.gemini_model,
            settings.gemini_timeout_seconds,
            fallback_model=settings.gemini_fallback_model,
        )
        yield
        if http_client is None:
            await client.aclose()

    # Interactive docs are disabled: they load third-party scripts that the
    # strict Content-Security-Policy blocks, and aren't needed in production.
    app = FastAPI(
        title="Fake Offer Letter & Phishing Inspector",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        """422 without FastAPI's default `input` echo, so submitted text is never reflected."""
        detail = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "Invalid input")} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": detail})

    def enforce_rate_limit(request: Request) -> None:
        """Dependency: per-IP sliding-window limit on the expensive endpoint."""
        key = client_ip(
            request.client.host if request.client else None,
            request.headers.get("x-forwarded-for"),
            settings.trusted_proxy_count,
        )
        retry_after = limiter.check(key)
        if retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail="Too many scans. Please wait a minute and try again.",
                headers={"Retry-After": str(int(retry_after + 0.999))},
            )

    @app.post("/api/scan", response_model=ScanReport, dependencies=[Depends(enforce_rate_limit)])
    async def scan(body: ScanRequest, request: Request) -> ScanReport:
        """Scan pasted text and/or a URL and return the Scam Threat Index.

        Nothing about the submission is stored or logged.
        """
        return await run_scan(
            body.text,
            body.url,
            request.app.state.extractor,
            request.app.state.http,
            settings.safe_browsing_api_key,
            page_fetcher,
        )

    @app.get("/api/samples", response_model=list[Sample])
    async def samples() -> tuple[Sample, ...]:
        """Built-in demo letters for one-click testing."""
        return SAMPLES

    @app.get("/api/status")
    async def status(request: Request) -> dict[str, bool | str]:
        """Which optional integrations are configured (never exposes keys)."""
        return {
            "gemini": request.app.state.extractor.enabled,
            "safe_browsing": settings.safe_browsing_api_key is not None,
            "model": settings.gemini_model,
            "fetch_linked_pages": page_fetcher is not None,
        }

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    index_file = static_dir / "index.html"

    @app.get("/", include_in_schema=False, response_model=None)
    async def index() -> FileResponse | HTMLResponse:
        """The single-page React UI (or a hint if it hasn't been built)."""
        if not index_file.is_file():
            return HTMLResponse(NOT_BUILT_PAGE, status_code=503)
        return FileResponse(index_file)

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon() -> FileResponse:
        """Site icon."""
        return FileResponse(static_dir / "favicon.svg", media_type="image/svg+xml")

    # Hashed JS/CSS/font bundles produced by Vite.
    app.mount("/assets", StaticFiles(directory=static_dir / "assets", check_dir=False), name="assets")
    return app


app = create_app()
