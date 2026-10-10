from __future__ import annotations

import math

from .config import (
    CAP_DISAGREEMENT_DELTA,
    LIKELY_AI_THRESHOLD,
    MIN_CONFIGURED_DETECTORS,
    NO_SIGNS_THRESHOLD,
)


def _agreement_level(spread: float) -> str:
    if spread <= 15:
        return "High"
    if spread <= CAP_DISAGREEMENT_DELTA:
        return "Medium"
    return "Low"


def evaluate_verdict(
    detector_scores: list[float],
    stability: float | None,
    quality: str,
    small_image: bool = False,
) -> dict:
    scores = [
        float(score)
        for score in detector_scores
        if isinstance(score, (int, float)) and math.isfinite(score) and 0 <= score <= 100
    ]
    sufficient_detectors = len(scores) >= MIN_CONFIGURED_DETECTORS
    score_mean = sum(scores) / len(scores) if sufficient_detectors else None
    spread = max(scores) - min(scores) if sufficient_detectors else None

    quality_low = quality in {"low", "moderate"}
    stability_low = stability is None or stability < 0.75
    disagreement = spread is not None and spread > CAP_DISAGREEMENT_DELTA
    capped = (
        not sufficient_detectors
        or quality_low
        or small_image
        or stability_low
        or disagreement
    )

    if capped:
        verdict = "Inconclusive"
    elif score_mean is not None and score_mean >= LIKELY_AI_THRESHOLD:
        verdict = "Likely AI"
    elif score_mean is not None and score_mean <= NO_SIGNS_THRESHOLD:
        verdict = "No AI signs found"
    else:
        verdict = "Inconclusive"

    if not sufficient_detectors or quality_low or small_image or stability_low or disagreement:
        evidence_strength = "Weak"
    elif len(scores) >= 3 and spread is not None and spread <= 15:
        evidence_strength = "Strong"
    else:
        evidence_strength = "Moderate"

    return {
        "verdict": verdict,
        "evidence_strength": evidence_strength,
        "agreement": _agreement_level(spread) if spread is not None else "Low",
        "mean_score": round(score_mean, 2) if score_mean is not None else None,
        "spread": round(spread, 2) if spread is not None else None,
        "stability": round(stability, 3) if stability is not None else None,
        "quality": quality,
        "small_image": small_image,
        "configured_detector_count": len(scores),
    }
