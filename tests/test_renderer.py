import base64

import pytest

from escpos_api.config import PrinterConfig
from escpos_api.models import ImageOptions, PrintJob
from escpos_api.renderer import RenderError, render_image, render_job

from .conftest import png_bytes

INIT = b"\x1b@"
PARTIAL_CUT = b"\x1dV\x01"
FULL_CUT = b"\x1dV\x00"


def render(*commands, printer=None, limits=None, **kw):
    job = PrintJob.model_validate({"commands": list(commands), **kw})
    return render_job(job, printer or PrinterConfig(name="p", host="h"), limits)


@pytest.fixture(autouse=True)
def _limits(limits, monkeypatch):
    global LIMITS
    LIMITS = limits


def r(*commands, **kw):
    return render(*commands, limits=LIMITS, **kw)


def test_starts_with_init_and_ends_with_auto_cut():
    out = r({"type": "text", "content": "hello\n"})
    assert out.startswith(INIT)
    assert b"hello\n" in out
    assert out.endswith(PARTIAL_CUT)


def test_no_auto_cut_when_disabled_or_present():
    assert PARTIAL_CUT not in r({"type": "text", "content": "x"}, cut=False)
    out = r({"type": "text", "content": "x"}, {"type": "cut", "mode": "full"})
    assert FULL_CUT in out
    assert PARTIAL_CUT not in out


def test_accents_and_euro():
    out = r({"type": "text", "content": "Café crème à 3,20 €\n"})
    assert b"?" not in out
    assert b"Caf\x82 cr\x8ame \x85 3,20 " in out  # CP437 for accents
    assert b"\x1bt" in out  # code page switch for €


def test_inline_style_is_temporary():
    out = r(
        {"type": "text", "content": "<A>", "bold": True},
        {"type": "text", "content": "<B>"},
    )
    a, b = out.index(b"<A>"), out.index(b"<B>")
    assert b"\x1bE\x01" in out[:a]  # bold on before A
    assert b"\x1bE\x00" in out[a:b]  # bold off restored before B


def test_persistent_style_and_reset():
    out = r(
        {"type": "style", "align": "center", "width": 2},
        {"type": "text", "content": "<A>"},
        {"type": "style", "reset": True},
        {"type": "text", "content": "<B>"},
    )
    a, b = out.index(b"<A>"), out.index(b"<B>")
    assert b"\x1ba\x01" in out[:a]  # center
    assert b"\x1d!\x10" in out[:a]  # double width
    assert b"\x1ba\x00" in out[a:b]  # back to left
    assert b"\x1d!\x00" in out[a:b]


@pytest.mark.parametrize("font, width, cols", [("a", 1, 48), ("b", 1, 64), ("a", 2, 24)])
def test_separator_fills_line(font, width, cols):
    out = r({"type": "style", "font": font, "width": width}, {"type": "separator", "char": "="})
    assert b"=" * cols + b"\n" in out
    assert b"=" * (cols + 1) not in out


def test_separator_small_printer():
    out = render(
        {"type": "separator"}, printer=PrinterConfig(name="s", host="h", width=384), limits=LIMITS
    )
    assert b"-" * 32 + b"\n" in out


def test_feed_and_cashdraw():
    out = r({"type": "feed", "lines": 3}, {"type": "cashdraw", "pin": 5})
    assert b"\n\n\n" in out
    assert b"\x1bp\x01" in out


def test_qr_keeps_commas():
    out = r({"type": "qr", "content": "a, b=1, c", "size": 4, "ec": "H"})
    assert b"a, b=1, c" in out
    assert b"\x1d(k\x03\x001C\x04" in out  # module size 4
    assert b"\x1d(k\x03\x001E3" in out  # EC level H


def test_barcodes():
    out = r(
        {"type": "barcode", "content": "4006381333931", "symbology": "EAN13"},
        {"type": "barcode", "content": "ABC-123", "symbology": "CODE128"},
        {"type": "barcode", "content": "A123B", "symbology": "CODABAR"},
    )
    assert b"4006381333931" in out
    assert b"{BABC-123" in out


def test_invalid_barcode_reports_index():
    with pytest.raises(RenderError) as exc:
        r(
            {"type": "text", "content": "x"},
            {"type": "barcode", "content": "12", "symbology": "EAN13"},
        )
    assert exc.value.status == 422
    assert exc.value.details[0]["index"] == 1
    assert exc.value.details[0]["type"] == "barcode"


def test_image_in_job():
    data = base64.b64encode(png_bytes(size=(1000, 100))).decode()
    out = r({"type": "image", "data": data})
    assert b"\x1dv0" in out  # raster bit image
    idx = out.index(b"\x1dv0")
    width_bytes = out[idx + 4] + out[idx + 5] * 256
    assert width_bytes == 576 // 8


def test_invalid_image_in_job_reports_index():
    data = base64.b64encode(b"definitely not an image").decode()
    with pytest.raises(RenderError) as exc:
        r({"type": "text", "content": "x"}, {"type": "image", "data": data})
    assert exc.value.details[0]["index"] == 1


def test_render_image_standalone():
    out = render_image(
        png_bytes(), ImageOptions(), True, PrinterConfig(name="p", host="h", width=384), LIMITS
    )
    assert out.startswith(INIT)
    assert b"\x1dv0" in out
    assert out.endswith(PARTIAL_CUT)
    out = render_image(
        png_bytes(), ImageOptions(), False, PrinterConfig(name="p", host="h"), LIMITS
    )
    assert PARTIAL_CUT not in out


@pytest.mark.parametrize("profile", ["default", "TM-T88V", "TM-T20II", "TM-P80"])
def test_image_works_with_any_profile(profile, capsys):
    printer = PrinterConfig(name="p", host="h", width=576, profile=profile)
    out = render_image(png_bytes(size=(2000, 50)), ImageOptions(), False, printer, LIMITS)
    assert b"\x1dv0" in out
    assert "media.width" not in capsys.readouterr().out
