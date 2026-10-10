from __future__ import annotations

from PIL import Image

from .config import MIN_IMAGE_PIXEL_COUNT, MIN_IMAGE_SIDE_PIXELS


def assess_quality(image_path: str) -> dict:
    with Image.open(image_path) as image:
        width, height = image.size
        pixel_count = width * height
        image_format = image.format
        mode = image.mode
        jpeg_quantization_table_count = (
            len(image.quantization) if image_format == "JPEG" and image.quantization else None
        )

    too_small = min(width, height) < MIN_IMAGE_SIDE_PIXELS or pixel_count < MIN_IMAGE_PIXEL_COUNT
    low_resolution = min(width, height) < MIN_IMAGE_SIDE_PIXELS
    quality = "low" if too_small else "good"
    warnings = []
    recommendation = None
    if too_small:
        warnings.append(
            "The image is small; results may be less reliable because resizing or compression can remove forensic traces."
        )
        recommendation = (
            "Ask the sender to share the original photo or document instead of a forwarded or compressed copy."
        )

    return {
        "resolution": f"{width}x{height}",
        "width": width,
        "height": height,
        "pixel_count": pixel_count,
        "format": image_format,
        "mode": mode,
        "jpeg_quantization_table_count": jpeg_quantization_table_count,
        "quality": quality,
        "low_resolution": low_resolution,
        "small_image": too_small,
        "warnings": warnings,
        "recommendation": recommendation,
    }
