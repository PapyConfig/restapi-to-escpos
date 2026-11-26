"""Safe image decoding and conversion to a printable 1-bit bitmap."""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import ApiError
from .models import ImageOptions

ALLOWED_FORMATS = {"PNG", "JPEG", "GIF", "BMP", "WEBP"}


class InvalidImage(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(422, "invalid_image", message)


@dataclass(frozen=True)
class ImageLimits:
    max_bytes: int
    max_pixels: int
    max_height: int


def decode(data: bytes, limits: ImageLimits) -> Image.Image:
    """Open an image after checking size, format and pixel count (before decoding)."""
    if len(data) > limits.max_bytes:
        raise ApiError(
            413, "payload_too_large", f"Image exceeds {limits.max_bytes // (1024 * 1024)} MB."
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(data), formats=sorted(ALLOWED_FORMATS))
            if img.width * img.height > limits.max_pixels:
                raise InvalidImage(
                    f"Image too large ({img.width}x{img.height}); "
                    f"maximum is {limits.max_pixels} pixels."
                )
            img.load()
    except InvalidImage:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidImage("Unsupported or unreadable image (PNG, JPEG, GIF, BMP, WebP).") from exc
    except (OSError, ValueError, SyntaxError) as exc:
        raise InvalidImage("Corrupted image file.") from exc
    return img


def to_bitmap(
    img: Image.Image, opts: ImageOptions, printer_width: int, max_height: int
) -> Image.Image:
    """Return a mode "1" image exactly `printer_width` wide, aligned with white margins."""
    img = ImageOps.exif_transpose(img)

    # Flatten transparency onto white.
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(background, rgba)
    img = img.convert("L")

    target = min(opts.width or printer_width, printer_width)
    if img.width > target or (opts.upscale and img.width < target):
        height = max(1, round(img.height * target / img.width))
        img = img.resize((target, height), Image.Resampling.LANCZOS)

    if img.height > max_height:  # too long a ticket: shrink to fit, keeping the ratio
        width = max(1, round(img.width * max_height / img.height))
        img = img.resize((width, max_height), Image.Resampling.LANCZOS)

    if opts.mode == "threshold":
        bitmap = img.point(lambda p: 255 if p >= opts.threshold else 0).convert(
            "1", dither=Image.Dither.NONE
        )
    else:
        bitmap = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)

    canvas = Image.new("1", (printer_width, bitmap.height), 255)
    free = printer_width - bitmap.width
    x = {"left": 0, "center": free // 2, "right": free}[opts.align]
    canvas.paste(bitmap, (x, 0))
    return canvas
