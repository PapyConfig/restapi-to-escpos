"""Public API contract: typed print commands, jobs and responses."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Align = Literal["left", "center", "right"]
Font = Literal["a", "b"]
ImageMode = Literal["dither", "threshold"]

MAX_COMMANDS = 500
MAX_TEXT = 10_000


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StyleFields(_Strict):
    align: Align | None = None
    bold: bool | None = None
    underline: Annotated[int, Field(ge=0, le=2)] | None = None
    font: Font | None = None
    width: Annotated[int, Field(ge=1, le=8, description="Character width multiplier")] | None = None
    height: Annotated[int, Field(ge=1, le=8, description="Character height multiplier")] | None = (
        None
    )
    invert: bool | None = None

    def style_values(self) -> dict[str, object]:
        return {k: v for k in StyleFields.model_fields if (v := getattr(self, k)) is not None}


class TextCommand(StyleFields):
    """Print text. Style fields apply to this text only."""

    type: Literal["text"]
    content: str = Field(min_length=1, max_length=MAX_TEXT)


class StyleCommand(StyleFields):
    """Change the current style until the next `style` command."""

    type: Literal["style"]
    reset: bool = False

    @model_validator(mode="after")
    def _not_empty(self) -> StyleCommand:
        if not self.reset and not self.style_values():
            raise ValueError("style needs at least one field, or reset=true")
        return self


class FeedCommand(_Strict):
    type: Literal["feed"]
    lines: int = Field(default=1, ge=1, le=255)


class SeparatorCommand(_Strict):
    type: Literal["separator"]
    char: str = Field(default="-", min_length=1, max_length=1)


class QrCommand(_Strict):
    type: Literal["qr"]
    content: str = Field(min_length=1, max_length=4000)
    size: int = Field(default=6, ge=1, le=16)
    ec: Literal["L", "M", "Q", "H"] = "M"
    align: Align = "center"


Symbology = Literal[
    "EAN13", "EAN8", "UPC-A", "UPC-E", "CODE39", "CODE93", "CODE128", "ITF", "CODABAR"
]


class BarcodeCommand(_Strict):
    type: Literal["barcode"]
    content: str = Field(min_length=1, max_length=255)
    symbology: Symbology = "CODE128"
    height: int = Field(default=80, ge=1, le=255)
    module_width: int = Field(default=3, ge=2, le=6)
    text_position: Literal["none", "above", "below", "both"] = "below"
    align: Align = "center"


class ImageOptions(_Strict):
    align: Align = "center"
    mode: ImageMode = "dither"
    threshold: int = Field(default=128, ge=0, le=255)
    width: int | None = Field(
        default=None, ge=8, le=2048, description="Target width in dots (≤ printer width)"
    )
    upscale: bool = Field(default=False, description="Allow enlarging small images to `width`")


class ImageCommand(ImageOptions):
    """Print an image embedded as base64 (PNG, JPEG, GIF, BMP, WebP)."""

    type: Literal["image"]
    data: str = Field(min_length=1, description="Base64-encoded image file")

    @field_validator("data")
    @classmethod
    def _base64(cls, v: str) -> str:
        if v.startswith("data:") and "," in v:  # tolerate data URLs
            v = v.split(",", 1)[1]
        try:
            base64.b64decode(v, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("data is not valid base64") from exc
        return v

    def image_bytes(self) -> bytes:
        return base64.b64decode(self.data)


class CutCommand(_Strict):
    type: Literal["cut"]
    mode: Literal["partial", "full"] = "partial"
    feed: bool = True


class CashdrawCommand(_Strict):
    type: Literal["cashdraw"]
    pin: Literal[2, 5] = 2


Command = Annotated[
    TextCommand
    | StyleCommand
    | FeedCommand
    | SeparatorCommand
    | QrCommand
    | BarcodeCommand
    | ImageCommand
    | CutCommand
    | CashdrawCommand,
    Field(discriminator="type"),
]

_JOB_EXAMPLE = {
    "printer": None,
    "cut": True,
    "commands": [
        {
            "type": "text",
            "content": "MA BOUTIQUE\n",
            "align": "center",
            "bold": True,
            "width": 2,
            "height": 2,
        },
        {"type": "separator"},
        {"type": "text", "content": "Café                  2,50 €\n"},
        {"type": "text", "content": "Croissant             1,20 €\n"},
        {"type": "separator", "char": "="},
        {"type": "text", "content": "TOTAL 3,70 €\n", "align": "right", "bold": True},
        {"type": "feed", "lines": 1},
        {"type": "qr", "content": "https://example.com/t/123, merci"},
        {"type": "cut"},
    ],
}


class PrintJob(_Strict):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [_JOB_EXAMPLE]})

    printer: str | None = Field(default=None, description="Printer name; default if omitted")
    cut: bool = Field(default=True, description="Append a partial cut unless the job ends with one")
    commands: list[Command] = Field(min_length=1, max_length=MAX_COMMANDS)


class PrintResult(BaseModel):
    job_id: str
    printer: str
    bytes: int
    duration_ms: int


class PrinterInfo(BaseModel):
    name: str
    host: str
    port: int
    width: int
    profile: str
    default: bool
    reachable: bool


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: list[dict[str, object]] | None = None


# -- built-in memo templates -------------------------------------------------------------

FieldType = Literal["text", "textarea", "date", "time", "select", "checkbox"]


class TemplateOption(BaseModel):
    value: str
    label: str


class TemplateField(BaseModel):
    key: str
    label: str
    type: FieldType
    required: bool = False
    max: int | None = Field(default=None, description="Maximum length of a text value")
    default: str | bool | None = Field(default=None, description="Used when the key is omitted")
    options: list[TemplateOption] | None = None
    placeholder: str | None = None
    auto: Literal["today", "now", "id"] | None = Field(
        default=None, description="Computed value (date, time, card id) when the key is omitted"
    )


class TemplateInfo(BaseModel):
    id: str
    name: str
    glyph: str
    description: str
    fields: list[TemplateField]


class TemplateRequest(_Strict):
    """Body of `/v1/templates/{id}/print`."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"values": {"taches": "Pain\nLait\nCafé"}}]},
    )

    printer: str | None = Field(default=None, description="Printer name; default if omitted")
    values: dict[str, object] = Field(
        default_factory=dict, description="Field values, validated against the template"
    )
    cut: bool = True
    now: datetime | None = Field(
        default=None,
        description="Local date and time printed on the ticket; server time if omitted",
    )
    seed: int | None = Field(
        default=None, ge=0, description="Makes random parts (quote) reproducible"
    )


class TemplateRenderRequest(TemplateRequest):
    """Body of `/v1/templates/{id}/render`."""

    partial: bool = Field(
        default=False,
        description="Preview while typing: required fields may be omitted or empty",
    )
