import re
from datetime import datetime

import pytest
from fastapi.exceptions import RequestValidationError

from escpos_api.config import PrinterConfig
from escpos_api.models import PrintJob, TemplateRequest
from escpos_api.renderer import render_job
from escpos_api.templates import (
    QUOTES,
    TEMPLATES,
    TEMPLATES_BY_ID,
    long_date,
    render_template,
    validate_values,
    wrap_words,
)

from .conftest import HEADERS, wait_jobs

NOW = datetime(2026, 11, 25, 14, 7)
WIDE = PrinterConfig(name="main", host="127.0.0.1", port=9100)
NARROW = PrinterConfig(name="small", host="127.0.0.1", port=9100, width=384)

SAMPLE = {
    "memo": {
        "titre": "Appeler le plombier",
        "message": "Avant jeudi, pour la fuite sous l'évier.",
        "signature": "Léo",
    },
    "todo": {
        "taches": "Sortir les poubelles\nRépondre à Paul au sujet de la réunion de jeudi "
        "prochain, sans faute\nRéserver le train",
        "echeance": "2026-11-27",
        "priorite": "haute",
    },
    "shopping": {"articles": "Lait\nPain\nTomates\nCafé\nBeurre doux", "magasin": "Marché"},
    "postit": {"texte": "CLÉS !", "inverse": True},
    "note": {"pour": "Camille", "message": "Il reste des lasagnes dans le frigo.", "de": "Léo"},
    "reminder": {
        "quoi": "Renouveler le passeport",
        "heure": "09:30",
        "lien": "https://example.org/rdv",
        "note": "Prendre deux photos.",
    },
    "wifi": {"ssid": "Maison;Invités", "password": 'p@ss:"1"'},
    "kanban": {"titre": "Migrer Traefik en v3", "projet": "homelab"},
    "journal": {"victoires": "Fini le rapport\nCouru 5 km\nAppelé mamie", "merci": "le soleil"},
    "quote": {},
}


def longest(template) -> dict[str, object]:
    """Every text field filled up to its maximum length with a mix of words and long words."""
    values: dict[str, object] = {}
    for f in template.fields:
        if f.type in ("text", "textarea") and f.max:
            values[f.key] = ("Supercalifragilistique é " * 200)[: f.max]
        elif f.type == "select":
            values[f.key] = f.options[-1].value
        elif f.type == "checkbox":
            values[f.key] = True
        elif f.type == "date":
            values[f.key] = "2026-09-30"
        elif f.type == "time":
            values[f.key] = "23:59"
    return values


def render(template_id: str, values: dict, printer=WIDE, **kw) -> PrintJob:
    request = TemplateRequest(**{"values": values, "now": NOW, "seed": 3, **kw})
    return render_template(TEMPLATES_BY_ID[template_id], request, printer)


def prints_as_is(text: str, printer: PrinterConfig, limits) -> bool:
    job = PrintJob(commands=[{"type": "text", "content": text}], cut=False)
    body = re.sub(rb"\x1bt.", b"", render_job(job, printer, limits)[2:])
    return body.count(b"?") == text.count("?")


def check_layout(job: PrintJob, printer: PrinterConfig, limits, label: str) -> None:
    for cmd in job.commands:
        assert cmd.type in ("text", "separator", "feed", "qr", "barcode"), cmd.type
        if cmd.type == "text":
            columns = printer.columns(cmd.font or "a", cmd.width or 1)
            for line in cmd.content.removesuffix("\n").split("\n"):
                assert len(line) <= columns, f"{label}: {len(line)} > {columns}: {line!r}"
        if cmd.type == "barcode":
            assert (11 * (len(cmd.content) + 3) + 2) * cmd.module_width <= printer.width
    texts = "".join(c.content for c in job.commands if c.type == "text")
    assert prints_as_is(texts, printer, limits), label
    assert render_job(job, printer, limits)


def test_ten_templates_with_unique_ids():
    assert len(TEMPLATES) == 10
    assert set(TEMPLATES_BY_ID) == set(SAMPLE)


@pytest.mark.parametrize("printer", [WIDE, NARROW], ids=["80mm", "58mm"])
@pytest.mark.parametrize("template_id", list(SAMPLE))
def test_template_layout(template_id, printer, limits):
    template = TEMPLATES_BY_ID[template_id]
    check_layout(render(template_id, SAMPLE[template_id], printer), printer, limits, "sample")
    check_layout(render(template_id, longest(template), printer), printer, limits, "longest")


@pytest.mark.parametrize("template_id", list(SAMPLE))
def test_partial_preview_with_no_values(template_id):
    request = TemplateRequest(values={}, now=NOW, seed=0)
    job = render_template(TEMPLATES_BY_ID[template_id], request, WIDE, partial=True)
    assert job.commands


def test_required_field_is_enforced_unless_partial():
    with pytest.raises(RequestValidationError) as exc:
        validate_values(TEMPLATES_BY_ID["memo"], {"message": "  "}, NOW)
    assert exc.value.errors()[0]["loc"] == ("body", "values", "message")
    assert validate_values(TEMPLATES_BY_ID["memo"], {}, NOW, partial=True)["message"] == ""


@pytest.mark.parametrize(
    ("template_id", "values", "key"),
    [
        ("memo", {"message": "x", "nope": "y"}, "nope"),
        ("memo", {"message": 3}, "message"),
        ("memo", {"message": "x", "date": "yes"}, "date"),
        ("memo", {"message": "x" * 2001}, "message"),
        ("todo", {"taches": "x", "priorite": "critique"}, "priorite"),
        ("todo", {"taches": "x", "echeance": "27/11/2026"}, "echeance"),
        ("todo", {"taches": "x", "echeance": "2026-02-31"}, "echeance"),
        ("reminder", {"quoi": "x", "heure": "24:00"}, "heure"),
    ],
)
def test_invalid_values(template_id, values, key):
    with pytest.raises(RequestValidationError) as exc:
        validate_values(TEMPLATES_BY_ID[template_id], values, NOW)
    assert exc.value.errors()[0]["loc"] == ("body", "values", key)


def test_defaults_and_auto_values_apply_to_omitted_keys_only():
    reminder = TEMPLATES_BY_ID["reminder"]
    assert validate_values(reminder, {"quoi": "x"}, NOW)["quand"] == "2026-11-25"
    assert validate_values(reminder, {"quoi": "x", "quand": ""}, NOW)["quand"] == ""
    kanban = validate_values(TEMPLATES_BY_ID["kanban"], {"titre": "x"}, NOW)
    assert kanban["id"] == "T-1125-1407"
    assert kanban["taille"] == "M"
    assert validate_values(TEMPLATES_BY_ID["memo"], {"message": "x"}, NOW)["date"] is True


def test_rendering_is_deterministic_for_now_and_seed():
    assert render("quote", {}) == render("quote", {})
    quotes = {render("quote", {}, seed=s).commands[1].content for s in range(len(QUOTES))}
    assert len(quotes) == len(QUOTES)


def test_french_dates():
    assert long_date(NOW) == "Mercredi 25 novembre 2026"
    assert long_date(datetime(2026, 8, 1)) == "Samedi 1 août 2026"
    stamp = render("memo", {"message": "x"}).commands[-1]
    assert stamp.content == "Mercredi 25 novembre 2026, 14h07\n"


def test_wifi_qr_escapes_special_characters():
    job = render("wifi", {"ssid": "a;b", "password": 'p:"', "hidden": True})
    qr = next(c for c in job.commands if c.type == "qr")
    assert qr.content == r"WIFI:T:WPA;S:a\;b;P:p\:\";H:true;;"
    job = render("wifi", {"ssid": "x", "security": "nopass"})
    assert next(c for c in job.commands if c.type == "qr").content == "WIFI:T:nopass;S:x;;"


def test_todo_has_a_box_per_task_and_an_urgent_band():
    job = render("todo", {"taches": "a\nb\n\nc", "priorite": "haute"})
    boxes = [c for c in job.commands if c.type == "text" and c.content.startswith("[ ] ")]
    assert len(boxes) == 3
    assert any(c.type == "text" and c.invert and "URGENT" in c.content for c in job.commands)


def test_kanban_falls_back_to_text_when_the_barcode_is_too_wide():
    job = render("kanban", {"titre": "x", "id": "ABCDEFGHIJKLMNOPQRST"}, NARROW)
    assert not any(c.type == "barcode" for c in job.commands)
    assert any(c.type == "text" and "ABCDEFGHIJ" in c.content for c in job.commands)
    job = render("kanban", {"titre": "x"}, NARROW)
    assert any(c.type == "barcode" for c in job.commands)


def test_wrap_words():
    assert wrap_words("un deux trois", 7) == ["un deux", "trois"]
    assert wrap_words("abcdefghij", 4) == ["abcd", "efgh", "ij"]
    assert wrap_words("a\n\nb", 10) == ["a", "", "b"]


def test_quotes_are_printable(limits):
    for quote, author in QUOTES:
        assert prints_as_is(quote + author, WIDE, limits)


# -- HTTP --------------------------------------------------------------------------------


async def test_list_templates(client):
    r = await client.get("/v1/templates", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert [t["id"] for t in body] == [t.id for t in TEMPLATES]
    todo = next(t for t in body if t["id"] == "todo")
    taches = next(f for f in todo["fields"] if f["key"] == "taches")
    assert taches["required"] is True
    assert taches["type"] == "textarea"
    priorite = next(f for f in todo["fields"] if f["key"] == "priorite")
    assert {"value": "haute", "label": "Haute"} in priorite["options"]


async def test_get_template(client):
    r = await client.get("/v1/templates/wifi", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["name"] == "Wi-Fi invités"


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", "/v1/templates/nope"),
        ("POST", "/v1/templates/nope/render"),
        ("POST", "/v1/templates/nope/print"),
    ],
)
async def test_unknown_template(client, printer, method, url):
    r = await client.request(method, url, json={}, headers=HEADERS)
    assert r.status_code == 404
    assert r.json()["error"] == "unknown_template"
    assert printer.connections == 0


@pytest.mark.parametrize(
    "url", ["/v1/templates", "/v1/templates/memo", "/v1/templates/memo/render"]
)
async def test_templates_require_the_key(client, url):
    method = "POST" if url.endswith("render") else "GET"
    r = await client.request(method, url, json={})
    assert r.status_code == 401


async def test_render_returns_a_job_accepted_by_print(client, printer):
    body = {"values": SAMPLE["todo"], "printer": "small", "now": "2026-11-25T14:07:00", "seed": 1}
    r = await client.post("/v1/templates/todo/render", json=body, headers=HEADERS)
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["printer"] == "small"
    assert job["cut"] is True
    assert job["commands"][0] == {
        "type": "text",
        "content": "   ! URGENT !   \n",
        "bold": True,
        "width": 2,
        "height": 2,
        "invert": True,
    }
    assert printer.connections == 0
    r = await client.post("/v1/print", json=job, headers=HEADERS)
    assert r.status_code == 200, r.text
    await wait_jobs(printer, 1)
    assert b"le train" in printer.jobs[0]


async def test_render_partial(client):
    r = await client.post("/v1/templates/memo/render", json={}, headers=HEADERS)
    assert r.status_code == 422
    r = await client.post("/v1/templates/memo/render", json={"partial": True}, headers=HEADERS)
    assert r.status_code == 200


async def test_print_template(client, printer):
    body = {"values": {"taches": "Pain\nLait"}}
    r = await client.post("/v1/templates/todo/print", json=body, headers=HEADERS)
    assert r.status_code == 200, r.text
    assert r.json()["printer"] == "main"
    await wait_jobs(printer, 1)
    assert b"[ ] Pain" in printer.jobs[0]
    assert b"\x1dV" in printer.jobs[0]  # cut


async def test_print_rejects_partial(client, printer):
    body = {"values": {}, "partial": True}
    r = await client.post("/v1/templates/memo/print", json=body, headers=HEADERS)
    assert r.status_code == 422
    assert printer.connections == 0


async def test_print_invalid_values_points_at_the_field(client, printer):
    body = {"values": {"taches": "x", "priorite": "critique"}}
    r = await client.post("/v1/templates/todo/print", json=body, headers=HEADERS)
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_job"
    assert r.json()["details"][0]["loc"] == ["body", "values", "priorite"]
    assert printer.connections == 0


async def test_print_unknown_printer(client, printer):
    body = {"values": {"message": "x"}, "printer": "nope"}
    r = await client.post("/v1/templates/memo/print", json=body, headers=HEADERS)
    assert r.status_code == 404
    assert r.json()["error"] == "unknown_printer"


@pytest.mark.parametrize("action", ["render", "print"])
async def test_foreign_origin_is_refused(client, printer, action):
    headers = {**HEADERS, "Origin": "https://evil.example"}
    body = {"values": {"message": "x"}}
    r = await client.post(f"/v1/templates/memo/{action}", json=body, headers=headers)
    assert r.status_code == 403
    assert printer.connections == 0
