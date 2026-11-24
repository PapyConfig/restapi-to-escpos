import io

import pytest
from PIL import Image

from escpos_api.errors import ApiError
from escpos_api.imaging import ImageLimits, InvalidImage, decode, to_bitmap
from escpos_api.models import ImageOptions

from .conftest import png_bytes


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "GIF", "BMP", "WEBP"])
def test_supported_formats(fmt, limits):
    assert decode(png_bytes(fmt=fmt), limits).size == (100, 50)


def test_rejects_non_images(limits):
    with pytest.raises(InvalidImage):
        decode(b"%PDF-1.4 not an image", limits)


def test_rejects_disallowed_format(limits):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "TIFF")
    with pytest.raises(InvalidImage):
        decode(buf.getvalue(), limits)


def test_rejects_truncated(limits):
    data = png_bytes(size=(500, 500), color=(10, 200, 30))
    with pytest.raises(InvalidImage):
        decode(data[: len(data) // 2], limits)


def test_rejects_too_many_pixels():
    limits = ImageLimits(max_bytes=10_000_000, max_pixels=1000, max_height=4000)
    with pytest.raises(InvalidImage, match="too large"):
        decode(png_bytes(size=(100, 100)), limits)


def test_rejects_too_many_bytes():
    limits = ImageLimits(max_bytes=10, max_pixels=10**9, max_height=4000)
    with pytest.raises(ApiError) as exc:
        decode(png_bytes(), limits)
    assert exc.value.status == 413


def test_downscale_to_printer_width():
    img = Image.new("L", (2000, 1000), 0)
    out = to_bitmap(img, ImageOptions(), 576, 4000)
    assert out.mode == "1"
    assert out.size == (576, 288)


def test_no_upscale_by_default_and_centered():
    img = Image.new("L", (100, 10), 0)
    out = to_bitmap(img, ImageOptions(), 576, 4000)
    assert out.size == (576, 10)
    row = [out.getpixel((x, 5)) for x in range(576)]
    black = [x for x, v in enumerate(row) if v == 0]
    assert (black[0], black[-1]) == (238, 337)


def test_upscale_and_target_width():
    img = Image.new("L", (100, 10), 0)
    out = to_bitmap(img, ImageOptions(width=300, upscale=True, align="left"), 576, 4000)
    black = [x for x in range(576) if out.getpixel((x, 5)) == 0]
    assert (black[0], black[-1]) == (0, 299)


def test_right_alignment():
    out = to_bitmap(Image.new("L", (100, 10), 0), ImageOptions(align="right"), 576, 4000)
    black = [x for x in range(576) if out.getpixel((x, 5)) == 0]
    assert (black[0], black[-1]) == (476, 575)


def test_transparency_prints_white():
    img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    out = to_bitmap(img, ImageOptions(), 384, 4000)
    assert out.getextrema() == (255, 255)


def test_threshold_vs_dither():
    grey = Image.new("L", (200, 20), 100)
    thr = to_bitmap(grey, ImageOptions(mode="threshold", threshold=128, align="left"), 200, 4000)
    assert thr.getextrema() == (0, 0)  # 100 < 128 -> black
    light = to_bitmap(grey, ImageOptions(mode="threshold", threshold=50), 200, 4000)
    assert light.getextrema() == (255, 255)
    dithered = to_bitmap(grey, ImageOptions(mode="dither"), 200, 4000)
    assert dithered.getextrema() == (0, 255)  # mix of black and white


def test_max_height():
    with pytest.raises(InvalidImage, match="high"):
        to_bitmap(Image.new("L", (100, 5000)), ImageOptions(), 576, 4000)


def test_exif_orientation():
    img = Image.new("L", (100, 20), 255)
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90°
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    out = to_bitmap(Image.open(io.BytesIO(buf.getvalue())), ImageOptions(), 576, 4000)
    assert out.height == 100
