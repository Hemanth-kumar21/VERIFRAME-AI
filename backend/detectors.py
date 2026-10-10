from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image

from .config import (
    DEMO_DETECTORS,
    DETECTOR_A_AI_LABEL,
    DETECTOR_A_MODEL,
    DETECTOR_B_AI_LABEL,
    DETECTOR_B_MODEL,
    DETECTOR_C_AI_LABEL,
    DETECTOR_C_MODEL,
    MIN_CONFIGURED_DETECTORS,
)


@lru_cache(maxsize=3)
def _load_classifier(model_id: str) -> Any:
    from transformers import pipeline

    import torch

    device = 0 if torch.cuda.is_available() else -1
    return pipeline("image-classification", model=model_id, device=device)


def _open_image(source: str | Path | Image.Image) -> Image.Image:
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    with Image.open(source) as image:
        return image.convert("RGB")


def _compute_demo_score(image: Image.Image, detector_name: str) -> float:
    import numpy as np

    thumb = image.copy()
    thumb.thumbnail((256, 256))
    try:
        rgb = np.array(thumb.convert("RGB"), dtype=float)
        gray = np.array(thumb.convert("L"), dtype=float)

        dx = np.diff(gray, axis=1)
        dy = np.diff(gray, axis=0)
        grad_mag = np.sqrt(dx[:-1, :] ** 2 + dy[:, :-1] ** 2)
        std_grad = float(np.std(grad_mag))

        max_c = np.max(rgb, axis=2)
        min_c = np.min(rgb, axis=2)
        sat = np.where(max_c > 0, (max_c - min_c) / (max_c + 1e-5), 0)
        avg_sat = float(np.mean(sat))

        if avg_sat > 0.4 and std_grad < 25:
            base_score = 88.0
        elif std_grad > 28:
            base_score = 15.0
        else:
            base_score = 50.0

        offset = 2.0 if detector_name == "detector_a" else -2.0
        return round(float(np.clip(base_score + offset, 5.0, 95.0)), 2)
    finally:
        thumb.close()


def _run_detector(
    name: str,
    model_id: str,
    ai_label: str,
    source: str | Path | Image.Image,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    result: dict[str, Any] = {
        "detector": name,
        "model": model_id or None,
        "score": None,
        "status": "not_configured",
        "latency_ms": 0,
    }
    if not model_id or not ai_label:
        result["message"] = "Configure both the model ID and its exact AI-class label to enable this detector."
        return result

    if model_id.lower().startswith("demo"):
        try:
            img = _open_image(source)
            try:
                score = _compute_demo_score(img, name)
            finally:
                img.close()
            return {
                "detector": name,
                "model": model_id,
                "score": score,
                "status": "ok",
                "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
            }
        except Exception:
            pass

    try:
        image = _open_image(source)
        try:
            predictions = _load_classifier(model_id)(image, top_k=None)
        finally:
            image.close()

        if predictions and isinstance(predictions[0], list):
            predictions = predictions[0]
        matching_scores = [
            float(prediction["score"])
            for prediction in predictions
            if str(prediction.get("label", "")).strip().casefold() == ai_label.casefold()
        ]
        if not matching_scores:
            result["status"] = "label_not_found"
            result["message"] = "The configured AI-class label was not returned by this model."
        else:
            score = max(matching_scores)
            if not 0 <= score <= 1:
                raise ValueError("Image-classification score must be between 0 and 1.")
            result["score"] = round(score * 100, 2)
            result["status"] = "ok"
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: detector inference failed."
    finally:
        result["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
    return result


def run_detector_a(source: str | Path | Image.Image) -> dict[str, Any]:
    return _run_detector("detector_a", DETECTOR_A_MODEL, DETECTOR_A_AI_LABEL, source)


def run_detector_b(source: str | Path | Image.Image) -> dict[str, Any]:
    return _run_detector("detector_b", DETECTOR_B_MODEL, DETECTOR_B_AI_LABEL, source)


def run_detector_c(source: str | Path | Image.Image) -> dict[str, Any]:
    return _run_detector("detector_c", DETECTOR_C_MODEL, DETECTOR_C_AI_LABEL, source)


def run_detector_ensemble(source: str | Path | Image.Image) -> dict[str, Any]:
    detectors = [run_detector_a(source), run_detector_b(source)]
    if DETECTOR_C_MODEL and DETECTOR_C_AI_LABEL:
        detectors.append(run_detector_c(source))
    seen_models = set()
    for detector in detectors:
        model_id = detector.get("model")
        if detector["status"] != "ok" or not model_id:
            continue
        if model_id in seen_models:
            detector["status"] = "duplicate_model"
            detector["score"] = None
            detector["message"] = "Each detector must use a different model ID."
        else:
            seen_models.add(model_id)
    scores = [
        entry["score"]
        for entry in detectors
        if entry["status"] == "ok" and entry["score"] is not None
    ]
    enough_detectors = len(scores) >= MIN_CONFIGURED_DETECTORS
    return {
        "detectors": detectors,
        "scores": scores,
        "average": round(sum(scores) / len(scores), 2) if enough_detectors else None,
        "status": "ok" if enough_detectors else "insufficient_detectors",
    }
