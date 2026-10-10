from __future__ import annotations

import io
import statistics

from PIL import Image, ImageOps

from .detectors import run_detector_ensemble


def run_robustness_checks(image_path: str) -> dict:
    with Image.open(image_path) as opened:
        base = opened.convert("RGB")
    try:
        half_size = (max(1, base.width // 2), max(1, base.height // 2))
        compressed_bytes = io.BytesIO()
        base.save(compressed_bytes, format="JPEG", quality=85)
        compressed_bytes.seek(0)
        with Image.open(compressed_bytes) as compressed:
            variants = {
                "original": base.copy(),
                "resized": base.resize(half_size),
                "center_crop": ImageOps.fit(base, half_size),
                "jpeg_recompressed": compressed.convert("RGB"),
                "horizontal_flip": ImageOps.mirror(base),
            }
    finally:
        base.close()

    scores_by_detector: dict[str, list[float]] = {}
    variant_results = {}
    try:
        for variant_name, variant in variants.items():
            try:
                result = run_detector_ensemble(variant)
                variant_results[variant_name] = result
                for detector in result["detectors"]:
                    if detector["status"] == "ok" and detector["score"] is not None:
                        scores_by_detector.setdefault(detector["detector"], []).append(
                            float(detector["score"])
                        )
            finally:
                variant.close()
    finally:
        compressed_bytes.close()

    stabilities = [
        1.0 - min(1.0, statistics.pstdev(scores) / 100.0)
        for scores in scores_by_detector.values()
        if len(scores) == len(variants)
    ]
    stability = round(sum(stabilities) / len(stabilities), 3) if stabilities else None
    return {
        "stability": stability,
        "scores_by_detector": scores_by_detector,
        "variants": variant_results,
        "label": "Detection stability across resized, center-cropped, JPEG-recompressed, and flipped variants.",
        "status": "ok" if stability is not None else "insufficient_detectors",
    }
