"""Server configuration, read exclusively from environment variables."""

from __future__ import annotations

from functools import cached_property
from typing import Annotated

from escpos.capabilities import CAPABILITIES
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PrinterName = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,31}$")]


class PrinterConfig(BaseModel):
    """A network ESC/POS printer declared on the server side."""

    name: PrinterName
    host: str = Field(min_length=1)
    port: int = Field(default=9100, ge=1, le=65535)
    width: int = Field(default=576, ge=64, le=2048, description="Printable width in dots")
    profile: str = "default"

    @field_validator("width")
    @classmethod
    def _multiple_of_8(cls, v: int) -> int:
        if v % 8:
            raise ValueError("width must be a multiple of 8")
        return v

    @field_validator("profile")
    @classmethod
    def _known_profile(cls, v: str) -> str:
        if v not in CAPABILITIES["profiles"]:
            raise ValueError(f"unknown python-escpos profile {v!r}")
        return v

    def columns(self, font: str, char_width: int = 1) -> int:
        """Number of characters per line for a font and a width multiplier."""
        dots = 12 if font == "a" else 9
        return max(1, self.width // (dots * char_width))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = ""
    allow_no_auth: bool = False

    printer_host: str | None = None
    printer_port: int = 9100
    printer_width: int = 576
    printer_profile: str = "default"
    printers: list[PrinterConfig] = Field(default_factory=list)
    default_printer: str | None = None
    printer_timeout: float = Field(default=10.0, gt=0, le=120)

    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    max_request_bytes: int = 15 * 1024 * 1024
    max_image_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 25_000_000
    max_image_height: int = 4000

    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _check(self) -> Settings:
        if not self.api_key and not self.allow_no_auth:
            raise ValueError(
                "API_KEY is not set. Set API_KEY (recommended) or ALLOW_NO_AUTH=true "
                "to run without authentication."
            )
        if self.printer_host and not self.printers:
            self.printers = [
                PrinterConfig(
                    name="default",
                    host=self.printer_host,
                    port=self.printer_port,
                    width=self.printer_width,
                    profile=self.printer_profile,
                )
            ]
        if not self.printers:
            raise ValueError("No printer configured: set PRINTER_HOST or PRINTERS.")
        names = [p.name for p in self.printers]
        if len(set(names)) != len(names):
            raise ValueError("Printer names in PRINTERS must be unique.")
        if self.default_printer is None:
            self.default_printer = names[0]
        elif self.default_printer not in names:
            raise ValueError(f"DEFAULT_PRINTER {self.default_printer!r} is not declared.")
        return self

    @cached_property
    def printers_by_name(self) -> dict[str, PrinterConfig]:
        return {p.name: p for p in self.printers}
