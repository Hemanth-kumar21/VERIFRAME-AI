from __future__ import annotations

import io
import warnings
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageFile, UnidentifiedImageError

from .config import ALLOWED_TYPES, MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS

ImageFile.LOAD_TRUNCATED_IMAGES = False
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

_EXTENSION_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}

_MIME_FORMATS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


def _read_magic(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "WEBP"
    return None


def validate_image_stream(
    fileobj: BinaryIO,
    filename: str,
    mime_type: str | None = None,
) -> dict:
    if fileobj is None:
        raise ValueError("No file uploaded.")

    binary = fileobj.read(MAX_IMAGE_BYTES + 1)
    if not binary:
        raise ValueError("The uploaded file is empty.")
    if len(binary) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image exceeds the {MAX_IMAGE_BYTES / (1024 * 1024):.0f} MB limit.")

    extension_format = _EXTENSION_FORMATS.get(Path(filename).suffix.lower())
    if extension_format is None:
        raise ValueError("Unsupported image extension. Allowed formats: JPG, JPEG, PNG, and WEBP.")

    if mime_type:
        mime_format = _MIME_FORMATS.get(mime_type.split(";", 1)[0].strip().lower())
        if mime_format is None:
            raise ValueError("Unsupported image MIME type. Allowed formats: JPEG, PNG, and WEBP.")
    else:
        mime_format = extension_format

    magic_format = _read_magic(binary)
    if magic_format is None:
        raise ValueError("Unsupported image type. Allowed formats: JPG, JPEG, PNG, and WEBP.")
    if magic_format not in ALLOWED_TYPES:
        raise ValueError("Only JPG, JPEG, PNG, or WEBP images are accepted.")
    if extension_format != magic_format or mime_format != magic_format:
        raise ValueError("The file extension, MIME type, and image contents do not match.")

    width = height = 0
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(binary)) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise ValueError("Image exceeds the maximum permitted pixel count.")
                image.verify()

            with Image.open(io.BytesIO(binary)) as image:
                image.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Image is too large and may be a decompression bomb attempt.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("The uploaded file is corrupt or not a valid image.") from exc

    return {
        "valid": True,
        "format": magic_format,
        "filename": Path(filename).name,
        "size_bytes": len(binary),
        "width": width,
        "height": height,
    }
