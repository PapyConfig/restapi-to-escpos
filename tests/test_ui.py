import re
from collections.abc import AsyncIterator

import httpx
import pytest

from escpos_api.config import PrinterConfig
from escpos_api.main import create_app
from escpos_api.models import PrintJob
from escpos_api.renderer import render_job
from escpos_api.ui import UI_DIR

from .conftest import HEADERS, make_settings, wait_jobs

TEXT_JOB = {"commands": [{"type": "text", "content": "Mémo\n"}]}


async def _client(port: int, **overrides) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(make_settings(port, **overrides))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://tickets.lan") as c:
        yield c


@pytest.fixture
async def ui_client(printer) -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(printer.port, ui_enabled=True):
        yield c


@pytest.mark.parametrize("path", ["/", "/ui", "/ui/", "/ui/app.js"])
async def test_ui_disabled_by_default(client, path):
    r = await client.get(path)
    assert r.status_code == 404


@pytest.mark.parametrize("path", ["/", "/ui"])
async def test_root_redirects_to_ui(ui_client, path):
    r = await ui_client.get(path)
    assert r.status_code == 307
    assert r.headers["location"] == "/ui/"


async def test_index_served_with_security_headers(ui_client):
    r = await ui_client.get("/ui/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert '<script type="module" src="app.js"></script>' in r.text
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"


@pytest.mark.parametrize(
    "name", ["app.js", "job.js", "preview.js", "templates.js", "storage.js", "style.css"]
)
async def test_static_assets(ui_client, name):
    r = await ui_client.get(f"/ui/{name}")
    assert r.status_code == 200
    assert "content-security-policy" in r.headers


EXTERNAL = re.compile(
    r"""(?:src|href)\s*=\s*["']?(?:https?:)?//|url\(\s*["']?(?:https?:)?//"""
    r"""|\bfrom\s+["'](?:https?:)?//|\bimport\s*\(\s*["'](?:https?:)?//|@import"""
)


async def test_ui_has_no_external_resources(ui_client):
    for path in sorted(UI_DIR.iterdir()):
        name = "" if path.name == "index.html" else path.name
        body = (await ui_client.get(f"/ui/{name}")).text
        assert not EXTERNAL.search(body), path.name


@pytest.mark.parametrize("path", ["/ui/nope.js", "/ui/../config.py", "/ui/%2e%2e/config.py"])
async def test_unknown_or_traversal_is_404(ui_client, path):
    r = await ui_client.get(path)
    assert r.status_code == 404


async def test_api_still_requires_key_with_ui(ui_client, printer):
    r = await ui_client.post("/v1/print", json=TEXT_JOB)
    assert r.status_code == 401
    assert printer.connections == 0


# -- origin check (always on) ------------------------------------------------------------


async def test_no_origin_is_allowed(client, printer):
    r = await client.post("/v1/print", json=TEXT_JOB, headers=HEADERS)
    assert r.status_code == 200


@pytest.mark.parametrize("origin", ["http://test", "https://test", "HTTPS://TEST/"])
async def test_same_origin_is_allowed(client, printer, origin):
    r = await client.post("/v1/print", json=TEXT_JOB, headers={**HEADERS, "Origin": origin})
    assert r.status_code == 200, r.text
    await wait_jobs(printer, 1)


@pytest.mark.parametrize(
    "origin", ["https://evil.example", "null", "http://test.evil", "file://", "https://test:8443"]
)
@pytest.mark.parametrize("url", ["/v1/print", "/v1/render"])
async def test_foreign_origin_is_refused(client, printer, origin, url):
    r = await client.post(url, json=TEXT_JOB, headers={**HEADERS, "Origin": origin})
    assert r.status_code == 403
    assert r.json()["error"] == "forbidden_origin"
    assert printer.connections == 0


async def test_foreign_origin_refused_on_image_upload(client, printer):
    r = await client.post(
        "/v1/print/image",
        files={"file": ("a.png", b"x", "image/png")},
        headers={**HEADERS, "Origin": "https://evil.example"},
    )
    assert r.status_code == 403
    assert printer.connections == 0


async def test_cors_origin_is_allowed(printer):
    async for c in _client(printer.port, cors_origins=["https://pos.lan"]):
        r = await c.post(
            "/v1/print", json=TEXT_JOB, headers={**HEADERS, "Origin": "https://pos.lan"}
        )
        assert r.status_code == 200, r.text


async def test_get_is_not_origin_checked(client):
    r = await client.get("/v1/printers", headers={**HEADERS, "Origin": "https://evil.example"})
    assert r.status_code == 200


# -- the UI's printable-character table matches the renderer ------------------------------


def _js_ranges() -> list[tuple[int, int]]:
    source = (UI_DIR / "job.js").read_text(encoding="utf-8")
    block = source.split("PRINTABLE_RANGES = [", 1)[1].split("];", 1)[0]
    return [
        (int(a, 16), int(b, 16)) for a, b in re.findall(r"\[0x([0-9A-F]+), 0x([0-9A-F]+)\]", block)
    ]


def _prints_as_is(char: str, printer: PrinterConfig, limits) -> bool:
    job = PrintJob(commands=[{"type": "text", "content": char}], cut=False)
    body = re.sub(rb"\x1bt.", b"", render_job(job, printer, limits)[2:])
    return b"?" not in body


def test_printable_ranges_match_renderer(main_printer, limits):
    ranges = _js_ranges()
    assert len(ranges) > 50
    for lo, hi in ranges:
        for cp in {lo, (lo + hi) // 2, hi}:
            assert _prints_as_is(chr(cp), main_printer, limits), f"U+{cp:04X} is not printable"
    # characters just outside the table really are unprintable
    for char in "☐✓★→♥":
        assert not _prints_as_is(char, main_printer, limits)
