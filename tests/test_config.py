import pytest
from pydantic import ValidationError

from escpos_api.config import PrinterConfig, Settings


def test_api_key_required(monkeypatch):
    with pytest.raises(ValidationError, match="API_KEY"):
        Settings(_env_file=None, printer_host="10.0.0.1")


def test_allow_no_auth():
    s = Settings(_env_file=None, allow_no_auth=True, printer_host="10.0.0.1")
    assert s.api_key == ""


def test_single_printer_shortcut_from_env(monkeypatch):
    monkeypatch.setenv("API_KEY", "k")
    monkeypatch.setenv("PRINTER_HOST", "10.0.0.5")
    monkeypatch.setenv("PRINTER_WIDTH", "384")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.lan, http://b.lan")
    s = Settings(_env_file=None)
    assert [(p.name, p.host, p.port, p.width) for p in s.printers] == [
        ("default", "10.0.0.5", 9100, 384)
    ]
    assert s.default_printer == "default"
    assert s.cors_origins == ["http://a.lan", "http://b.lan"]


def test_printers_json_from_env(monkeypatch):
    monkeypatch.setenv("API_KEY", "k")
    monkeypatch.setenv(
        "PRINTERS", '[{"name":"caisse","host":"10.0.0.5"},{"name":"cuisine","host":"10.0.0.6"}]'
    )
    monkeypatch.setenv("DEFAULT_PRINTER", "cuisine")
    s = Settings(_env_file=None)
    assert list(s.printers_by_name) == ["caisse", "cuisine"]
    assert s.default_printer == "cuisine"


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({}, "No printer"),
        ({"printer_host": "h", "default_printer": "nope"}, "DEFAULT_PRINTER"),
        (
            {"printers": [{"name": "a", "host": "h"}, {"name": "a", "host": "i"}]},
            "unique",
        ),
    ],
)
def test_invalid_settings(kwargs, match):
    with pytest.raises(ValidationError, match=match):
        Settings(_env_file=None, api_key="k", **kwargs)


@pytest.mark.parametrize(
    "kwargs", [{"width": 500}, {"profile": "nope"}, {"name": "Bad Name"}, {"port": 0}]
)
def test_invalid_printer(kwargs):
    with pytest.raises(ValidationError):
        PrinterConfig(**{"name": "p", "host": "h", **kwargs})


def test_columns():
    p = PrinterConfig(name="p", host="h", width=576)
    assert p.columns("a") == 48
    assert p.columns("b") == 64
    assert p.columns("a", 2) == 24


def test_ui_disabled_by_default_and_enabled_from_env(monkeypatch):
    monkeypatch.setenv("API_KEY", "k")
    monkeypatch.setenv("PRINTER_HOST", "10.0.0.5")
    assert Settings(_env_file=None).ui_enabled is False
    monkeypatch.setenv("UI_ENABLED", "true")
    assert Settings(_env_file=None).ui_enabled is True
