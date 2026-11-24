import asyncio
import base64
import json
from pathlib import Path

import httpx
import pytest

from escpos_api.main import create_app

from .conftest import API_KEY, HEADERS, free_port, make_settings, png_bytes, wait_jobs

EXAMPLES = Path(__file__).parent.parent / "examples"
TEXT_JOB = {"commands": [{"type": "text", "content": "Bonjour €\n"}]}


async def test_health_is_public(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
@pytest.mark.parametrize(
    "method, url", [("GET", "/v1/printers"), ("POST", "/v1/print"), ("POST", "/v1/render")]
)
async def test_auth_required(client, printer, method, url, headers):
    r = await client.request(method, url, json=TEXT_JOB, headers=headers)
    assert r.status_code == 401
    assert r.json()["error"] == "unauthorized"
    assert printer.connections == 0


async def test_print_job(client, printer):
    r = await client.post("/v1/print", json=TEXT_JOB, headers=HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["printer"] == "main"
    await wait_jobs(printer, 1)
    assert len(printer.jobs[0]) == body["bytes"]
    assert printer.jobs[0].startswith(b"\x1b@")


async def test_named_printer_and_unknown(client, printer):
    r = await client.post("/v1/print", json={**TEXT_JOB, "printer": "small"}, headers=HEADERS)
    assert r.json()["printer"] == "small"
    r = await client.post("/v1/print", json={**TEXT_JOB, "printer": "nope"}, headers=HEADERS)
    assert r.status_code == 404
    assert r.json()["error"] == "unknown_printer"


async def test_invalid_schema_sends_nothing(client, printer):
    job = {"commands": [{"type": "text", "content": "ok"}, {"type": "blink"}]}
    r = await client.post("/v1/print", json=job, headers=HEADERS)
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_job"
    assert r.json()["details"]
    assert printer.connections == 0


async def test_render_error_sends_nothing(client, printer):
    job = {
        "commands": [
            {"type": "text", "content": "ok"},
            {"type": "barcode", "content": "1", "symbology": "EAN13"},
        ]
    }
    r = await client.post("/v1/print", json=job, headers=HEADERS)
    assert r.status_code == 422
    assert r.json()["details"][0]["index"] == 1
    assert printer.connections == 0


async def test_unreachable_printer():
    app = create_app(make_settings(free_port()))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/v1/print", json=TEXT_JOB, headers=HEADERS)
        assert r.status_code == 502
        assert r.json()["error"] == "printer_unreachable"
        printers = (await c.get("/v1/printers", headers=HEADERS)).json()
        assert [p["reachable"] for p in printers] == [False, False]


async def test_timeout_does_not_block_other_requests(printer, monkeypatch):
    import escpos_api.transport as transport_mod

    async def hang(*args, **kwargs):
        await asyncio.sleep(30)

    monkeypatch.setattr(transport_mod.asyncio, "open_connection", hang)
    app = create_app(make_settings(printer.port, printer_timeout=0.5))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        task = asyncio.create_task(c.post("/v1/print", json=TEXT_JOB, headers=HEADERS))
        await asyncio.sleep(0.1)
        health = await c.get("/health")
        assert health.status_code == 200
        assert not task.done()
        r = await task
    assert r.status_code == 504
    assert r.json()["error"] == "printer_timeout"


async def test_list_printers(client):
    r = await client.get("/v1/printers", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert [(p["name"], p["default"], p["reachable"], p["width"]) for p in data] == [
        ("main", True, True, 576),
        ("small", False, True, 384),
    ]


async def test_concurrent_jobs_all_printed(client, printer):
    jobs = [{"commands": [{"type": "text", "content": f"<job {i}>\n"}]} for i in range(10)]
    rs = await asyncio.gather(*(client.post("/v1/print", json=j, headers=HEADERS) for j in jobs))
    assert all(r.status_code == 200 for r in rs)
    await wait_jobs(printer, 10)
    for i in range(10):
        assert sum(f"<job {i}>".encode() in j for j in printer.jobs) == 1


async def test_print_image_upload(client, printer):
    files = {"file": ("logo.png", (EXAMPLES / "logo.png").read_bytes(), "image/png")}
    r = await client.post(
        "/v1/print/image", files=files, data={"align": "left", "printer": "small"}, headers=HEADERS
    )
    assert r.status_code == 200, r.text
    await wait_jobs(printer, 1)
    job = printer.jobs[0]
    idx = job.index(b"\x1dv0")
    assert job[idx + 4] + job[idx + 5] * 256 == 384 // 8
    assert job.endswith(b"\x1dV\x01")


async def test_print_image_no_cut(client, printer):
    files = {"file": ("a.jpg", png_bytes(fmt="JPEG"), "image/jpeg")}
    r = await client.post("/v1/print/image", files=files, data={"cut": "false"}, headers=HEADERS)
    assert r.status_code == 200
    await wait_jobs(printer, 1)
    assert not printer.jobs[0].endswith(b"\x1dV\x01")


async def test_print_image_rejects_non_image(client, printer):
    files = {"file": ("x.png", b"<?php echo 1; ?>", "image/png")}
    r = await client.post("/v1/print/image", files=files, headers=HEADERS)
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_image"
    assert printer.connections == 0


async def test_print_image_bad_option(client, printer):
    files = {"file": ("a.png", png_bytes(), "image/png")}
    r = await client.post("/v1/print/image", files=files, data={"mode": "x"}, headers=HEADERS)
    assert r.status_code == 422
    assert printer.connections == 0


async def test_image_too_big(printer):
    app = create_app(make_settings(printer.port, max_image_bytes=100))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        files = {"file": ("a.png", png_bytes(size=(300, 300), color=(1, 2, 3)), "image/png")}
        r = await c.post("/v1/print/image", files=files, headers=HEADERS)
    assert r.status_code == 413
    assert printer.connections == 0


async def test_body_limit(printer):
    app = create_app(make_settings(printer.port, max_request_bytes=1000))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        big = {"commands": [{"type": "text", "content": "x" * 5000}]}
        r = await c.post("/v1/print", json=big, headers=HEADERS)
        assert r.status_code == 413
        assert r.json()["error"] == "payload_too_large"

        async def chunks():
            yield json.dumps(big).encode()

        r = await c.post(
            "/v1/print",
            content=chunks(),
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        assert r.status_code == 413
    assert printer.connections == 0


async def test_render_does_not_connect(client, printer):
    job = json.loads((EXAMPLES / "full-receipt.json").read_text())
    r = await client.post("/v1/render", json=job, headers=HEADERS)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/octet-stream"
    assert int(r.headers["x-escpos-bytes"]) == len(r.content) > 1000
    assert printer.connections == 0


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.json")), ids=lambda p: p.name)
async def test_examples_print(client, printer, path):
    r = await client.post("/v1/print", json=json.loads(path.read_text()), headers=HEADERS)
    assert r.status_code == 200, r.text


async def test_cors_disabled_by_default(client):
    r = await client.options(
        "/v1/print",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in r.headers


async def test_cors_allowlist(printer):
    app = create_app(make_settings(printer.port, cors_origins=["http://pos.lan"]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.options(
            "/v1/print",
            headers={"Origin": "http://pos.lan", "Access-Control-Request-Method": "POST"},
        )
        assert r.headers["access-control-allow-origin"] == "http://pos.lan"


async def test_no_auth_mode(printer):
    app = create_app(make_settings(printer.port, api_key="", allow_no_auth=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/v1/print", json=TEXT_JOB)
    assert r.status_code == 200


async def test_internal_errors_are_generic(client, monkeypatch):
    import escpos_api.api as api

    def boom(*a, **k):
        raise RuntimeError("secret /etc/path detail")

    monkeypatch.setattr(api, "render_job", boom)
    transport = httpx.ASGITransport(app=client._transport.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/v1/print", json=TEXT_JOB, headers=HEADERS)
    assert r.status_code == 500
    assert "secret" not in r.text
    assert r.json()["error"] == "internal_error"


async def test_openapi(client):
    schema = (await client.get("/openapi.json")).json()
    assert {"/v1/print", "/v1/print/image", "/v1/render", "/v1/printers"} <= set(schema["paths"])
    assert API_KEY not in json.dumps(schema)


def test_image_base64_roundtrip_example():
    job = json.loads((EXAMPLES / "full-receipt.json").read_text())
    data = job["commands"][0]["data"]
    assert base64.b64decode(data) == (EXAMPLES / "logo.png").read_bytes()
