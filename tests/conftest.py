"""Shared fixtures."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def static_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A minimal stand-in for the Vite build, so backend tests don't need `npm run build`."""
    root = tmp_path_factory.mktemp("dist")
    (root / "assets").mkdir()
    (root / "index.html").write_text(
        '<!DOCTYPE html><title>Offer Letter Inspector</title><div id="root"></div>'
        '<script type="module" src="/assets/app.js"></script>',
        encoding="utf-8",
    )
    (root / "assets" / "app.js").write_text("console.log('ui');", encoding="utf-8")
    (root / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    return root
