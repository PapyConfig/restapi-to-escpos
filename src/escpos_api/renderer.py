"""Render a validated print job into a complete ESC/POS byte stream (no I/O)."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, replace

from escpos.exceptions import Error as EscposError
from escpos.printer import Dummy

from .config import PrinterConfig
from .errors import ApiError
from .imaging import ImageLimits, InvalidImage, decode, to_bitmap
from .models import (
    BarcodeCommand,
    CashdrawCommand,
    Command,
    CutCommand,
    FeedCommand,
    ImageCommand,
    ImageOptions,
    PrintJob,
    QrCommand,
    SeparatorCommand,
    StyleCommand,
    StyleFields,
    TextCommand,
)

# python-escpos logs every hardware barcode at INFO level.
logging.getLogger("escpos").setLevel(logging.WARNING)

_QR_EC = {"L": 0, "M": 1, "Q": 2, "H": 3}
_BARCODE_POS = {"none": "OFF", "above": "ABOVE", "below": "BELOW", "both": "BOTH"}
_BARCODE_TYPE = {"CODABAR": "NW7"}


@dataclass(frozen=True)
class Style:
    align: str = "left"
    bold: bool = False
    underline: int = 0
    font: str = "a"
    width: int = 1
    height: int = 1
    invert: bool = False

    def merged(self, fields: StyleFields) -> Style:
        return replace(self, **fields.style_values())


class RenderError(ApiError):
    def __init__(self, index: int, kind: str, reason: str) -> None:
        super().__init__(
            422,
            "invalid_job",
            f"Command #{index} ({kind}) cannot be rendered: {reason}",
            details=[{"index": index, "type": kind, "reason": reason}],
        )


class Renderer:
    def __init__(self, printer: PrinterConfig, limits: ImageLimits) -> None:
        self.printer = printer
        self.limits = limits
        self.out = Dummy(profile=printer.profile)
        # The printable width comes from our configuration, not from the profile (whose
        # width may be unknown or differ); copy so the shared profile class is untouched.
        data = copy.deepcopy(self.out.profile.profile_data)
        data.setdefault("media", {}).setdefault("width", {})["pixels"] = printer.width
        self.out.profile.profile_data = data
        self.style = Style()

    # -- helpers ---------------------------------------------------------------

    def _apply(self, style: Style) -> None:
        self.out.set(
            align=style.align,
            font=style.font,
            bold=style.bold,
            underline=style.underline,
            invert=style.invert,
            custom_size=True,
            width=style.width,
            height=style.height,
        )

    def _image(self, data: bytes, opts: ImageOptions) -> None:
        img = decode(data, self.limits)
        bitmap = to_bitmap(img, opts, self.printer.width, self.limits.max_height)
        self.out.image(bitmap, impl="bitImageRaster")

    # -- commands --------------------------------------------------------------

    def _render(self, cmd: Command) -> None:
        match cmd:
            case TextCommand():
                temp = self.style.merged(cmd)
                if temp != self.style:
                    self._apply(temp)
                self.out.text(cmd.content)
                if temp != self.style:
                    self._apply(self.style)
            case StyleCommand():
                base = Style() if cmd.reset else self.style
                self.style = base.merged(cmd)
                self._apply(self.style)
            case FeedCommand():
                self.out.ln(cmd.lines)
            case SeparatorCommand():
                cols = self.printer.columns(self.style.font, self.style.width)
                self.out.text(cmd.char * cols + "\n")
            case QrCommand():
                self.out.set(align=cmd.align)
                self.out.qr(cmd.content, size=cmd.size, ec=_QR_EC[cmd.ec], native=True)
                self.out.set(align=self.style.align)
            case BarcodeCommand():
                content = cmd.content
                if cmd.symbology == "CODE128" and not content.startswith("{"):
                    content = "{B" + content
                self.out.set(align=cmd.align)
                self.out.barcode(
                    content,
                    _BARCODE_TYPE.get(cmd.symbology, cmd.symbology),
                    height=cmd.height,
                    width=cmd.module_width,
                    pos=_BARCODE_POS[cmd.text_position],
                    align_ct=False,
                )
                self.out.set(align=self.style.align)
            case ImageCommand():
                self._image(cmd.image_bytes(), cmd)
            case CutCommand():
                self.out.cut(mode="FULL" if cmd.mode == "full" else "PART", feed=cmd.feed)
            case CashdrawCommand():
                self.out.cashdraw(cmd.pin)

    def render_job(self, job: PrintJob) -> bytes:
        self.out.hw("INIT")
        for index, cmd in enumerate(job.commands):
            try:
                self._render(cmd)
            except InvalidImage as exc:
                raise RenderError(index, cmd.type, exc.message) from exc
            except ApiError:
                raise
            except (EscposError, ValueError, TypeError) as exc:
                raise RenderError(index, cmd.type, str(exc) or type(exc).__name__) from exc
        if job.cut and not isinstance(job.commands[-1], CutCommand):
            self.out.cut(mode="PART")
        return self.out.output

    def render_image(self, data: bytes, opts: ImageOptions, cut: bool) -> bytes:
        self.out.hw("INIT")
        self._image(data, opts)
        if cut:
            self.out.cut(mode="PART")
        return self.out.output


def render_job(job: PrintJob, printer: PrinterConfig, limits: ImageLimits) -> bytes:
    return Renderer(printer, limits).render_job(job)


def render_image(
    data: bytes, opts: ImageOptions, cut: bool, printer: PrinterConfig, limits: ImageLimits
) -> bytes:
    return Renderer(printer, limits).render_image(data, opts, cut)
