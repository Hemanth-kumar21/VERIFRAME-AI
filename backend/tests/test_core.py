import io

import pytest
from PIL import Image

from backend.verdict import evaluate_verdict
from backend.validation import validate_image_stream


def make_image(size=(200, 200), color=(255, 0, 0), fmt="PNG"):
    image = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    buffer.seek(0)
    return buffer


def test_verdict_handles_disagreement_and_quality_cap():
    verdict = evaluate_verdict(
        detector_scores=[90, 10],
        stability=0.85,
        quality="low",
        small_image=False,
    )
    assert verdict["verdict"] == "Inconclusive"

    verdict = evaluate_verdict(detector_scores=[90, 92], stability=0.1, quality="good", small_image=False)
    assert verdict["verdict"] == "Inconclusive"

    verdict = evaluate_verdict(detector_scores=[90, 90], stability=0.99, quality="good", small_image=False)
    assert verdict["verdict"] == "Likely AI"


def test_validate_image_accepts_valid_png_and_rejects_bad_ones():
    good = make_image()
    result = validate_image_stream(good, "test.png")
    assert result["valid"] is True

    bad_type = io.BytesIO(b"not an image")
    with pytest.raises(ValueError):
        validate_image_stream(bad_type, "bad.txt")

    huge = make_image((6000, 6000))
    with pytest.raises(ValueError):
        validate_image_stream(huge, "huge.png")
