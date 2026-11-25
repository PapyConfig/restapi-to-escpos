"""Image delivery settings (fragmentation, image command, close grace)."""

import pytest
from pydantic import ValidationError

from escpos_api.config import PrinterConfig, Settings


def test_image_settings_from_env(monkeypatch):
    monkeypatch.setenv("API_KEY", "k")
    monkeypatch.setenv("PRINTER_HOST", "10.0.0.5")
    monkeypatch.setenv("PRINTER_IMAGE_IMPL", "bitImageColumn")
    monkeypatch.setenv("PRINTER_IMAGE_FRAGMENT_HEIGHT", "240")
    monkeypatch.setenv("PRINTER_CLOSE_GRACE", "2")
    s = Settings(_env_file=None)
    assert s.printers[0].image_impl == "bitImageColumn"
    assert s.printers[0].image_fragment_height == 240
    assert s.printer_close_grace == 2


def test_image_defaults():
    p = PrinterConfig(name="p", host="h")
    assert (p.image_impl, p.image_fragment_height) == ("bitImageRaster", 128)
    with pytest.raises(ValidationError):
        PrinterConfig(name="p", host="h", image_impl="sixel")
