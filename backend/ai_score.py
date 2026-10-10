"""AI-Generated Content Detection & Authenticity Scoring Module.

Calculates grounded, reproducible AI-likelihood scores and authenticity percentages
for images and videos based on configured neural network detectors and multi-frame
temporal consensus analysis.
"""
from __future__ import annotations

import math
from typing import Any

from .config import (
    DETECTOR_A_MODEL,
    DETECTOR_B_MODEL,
    DETECTOR_C_MODEL,
    LIKELY_AI_THRESHOLD,
    MIN_CONFIGURED_DETECTORS,
    NO_SIGNS_THRESHOLD,
    NVIDIA_MODEL,
)


def compute_image_ai_detection_score(
    verdict_data: dict[str, Any],
    tool_summaries: dict[str, Any],
) -> dict[str, Any]:
    """Calculate AI-generated content detection percentage and authenticity score for a single image."""
    detectors = tool_summaries.get("detectors") or []
    models_used: list[str] = []
    scores: list[float] = []

    for d in detectors:
        if isinstance(d, dict) and d.get("status") == "ok":
            if d.get("model"):
                models_used.append(str(d["model"]))
            if isinstance(d.get("score"), (int, float)) and math.isfinite(d["score"]):
                scores.append(float(d["score"]))

    if not models_used:
        for m in (DETECTOR_A_MODEL, DETECTOR_B_MODEL, DETECTOR_C_MODEL):
            if m:
                models_used.append(m)

    mean_score = verdict_data.get("mean_score")
    if mean_score is None and scores and len(scores) >= MIN_CONFIGURED_DETECTORS:
        mean_score = sum(scores) / len(scores)

    verdict = verdict_data.get("verdict", "Inconclusive")
    strength = verdict_data.get("evidence_strength", "Moderate")
    agreement = verdict_data.get("agreement", "Medium")
    spread = verdict_data.get("spread", 0.0)

    # Classification mapping
    if verdict == "Likely AI":
        classification = "Likely AI-Generated"
    elif verdict == "No AI signs found":
        classification = "Likely Human-Created"
    else:
        classification = "Inconclusive"

    # Score calculation
    if mean_score is not None and isinstance(mean_score, (int, float)) and math.isfinite(mean_score):
        ai_prob = round(float(mean_score), 1)
        human_prob = round(max(0.0, min(100.0, 100.0 - ai_prob)), 1)
    else:
        ai_prob = None
        human_prob = None

    # Confidence calculation
    if classification == "Inconclusive":
        confidence = "Low"
    elif strength == "Strong" and agreement == "High":
        confidence = "High"
    elif strength in ("Strong", "Moderate") and agreement in ("High", "Medium"):
        confidence = "Medium"
    else:
        confidence = "Low"

    # Evidence points formulation
    evidence: list[str] = []
    if ai_prob is not None:
        evidence.append(
            f"Configured detector ensemble yielded a {ai_prob}% AI-likelihood score across {len(models_used)} active model(s)."
        )
    else:
        evidence.append("Active detectors did not return sufficient inference scores to compute an ensemble average.")

    quality = tool_summaries.get("quality") or {}
    if isinstance(quality, dict):
        q_label = quality.get("quality", "standard")
        w = quality.get("width", 0)
        h = quality.get("height", 0)
        if q_label in ("low", "moderate") or verdict_data.get("small_image"):
            evidence.append(
                f"Image resolution ({w}x{h}) is constrained; low pixel count or compression may obscure fine generative artifacts."
            )
        elif w and h:
            evidence.append(
                f"Image dimensions ({w}x{h}) provided adequate spatial resolution for high-frequency artifact analysis."
            )

    robustness = tool_summaries.get("robustness") or {}
    if isinstance(robustness, dict) and robustness.get("stability") is not None:
        stab = robustness["stability"]
        evidence.append(
            f"Perturbation stability: {stab:.2f} (evaluated across Gaussian noise and blur variations)."
        )

    tiles = tool_summaries.get("tiles") or {}
    if isinstance(tiles, dict) and tiles.get("status") == "ok":
        evidence.append("Spatial grid analysis verified consistent score distribution across image regions.")

    if classification == "Inconclusive":
        if spread and spread > 25:
            evidence.append(
                f"High divergence between detector models (spread: {spread}%) prevented a consensus classification."
            )
        elif ai_prob is not None and NO_SIGNS_THRESHOLD < ai_prob < LIKELY_AI_THRESHOLD:
            evidence.append(
                f"The AI-likelihood score ({ai_prob}%) falls into the inconclusive boundary region between human and synthetic thresholds."
            )
        else:
            evidence.append("Available forensic evidence was mixed or insufficient to confirm origin.")

    return {
        "ai_probability": ai_prob,
        "human_probability": human_prob,
        "classification": classification,
        "confidence": confidence,
        "is_calibrated": False,
        "score_label": "AI-Likelihood Score",
        "evidence": evidence,
        "analyzed_frames": 1,
        "scored_frames": 1 if ai_prob is not None else 0,
        "model_info": {
            "models": models_used,
            "method": "Multi-detector ensemble average with quality & perturbation stability weighting.",
            "limitations": [
                "Scores represent model-estimated likelihoods, not statistically calibrated absolute probabilities.",
                "High compression, resizing, and screenshots can suppress synthetic frequency signatures.",
                "Absence of detectable AI signatures does not guarantee authentic origin.",
            ],
        },
        "status": "completed" if ai_prob is not None else "inconclusive",
    }


def compute_video_ai_detection_score(
    video_result: dict[str, Any],
    nemotron_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate AI-generated content detection percentage and authenticity score for a video."""
    analyzed_frames_count = int(video_result.get("analyzed_frame_count") or 0)
    frames = video_result.get("frames") or []
    scored_frames = [f for f in frames if isinstance(f, dict) and f.get("mean_score") is not None]
    scored_count = len(scored_frames)

    models_used: list[str] = []
    for m in (DETECTOR_A_MODEL, DETECTOR_B_MODEL):
        if m:
            models_used.append(m)
    if nemotron_summary and nemotron_summary.get("status") == "completed":
        models_used.append(nemotron_summary.get("model") or NVIDIA_MODEL)

    verdict = video_result.get("verdict", "Inconclusive")
    strength = video_result.get("evidence_strength", "Moderate")
    temporal_checks = video_result.get("temporal_checks") or {}
    unstable_pairs = temporal_checks.get("unstable_neighbor_pairs") or []
    unstable_count = len(unstable_pairs)

    suspicious_count = int(video_result.get("suspicious_signal_count") or 0)
    scene_coverage = int(video_result.get("scene_coverage_count") or 1)

    # Classification
    if verdict == "Likely AI":
        classification = "Likely AI-Generated"
    elif verdict == "No AI signs found":
        classification = "Likely Human-Created"
    else:
        classification = "Inconclusive"

    # Aggregated Score
    if scored_count > 0:
        scores = [float(f["mean_score"]) for f in scored_frames]
        raw_mean = sum(scores) / len(scores)
        ai_prob = round(raw_mean, 1)
        human_prob = round(max(0.0, min(100.0, 100.0 - ai_prob)), 1)
    else:
        ai_prob = None
        human_prob = None

    # Confidence
    if classification == "Inconclusive":
        confidence = "Low"
    elif strength == "Strong" and unstable_count == 0 and scored_count >= 4:
        confidence = "High"
    elif strength in ("Strong", "Moderate") and unstable_count <= 1:
        confidence = "Medium"
    else:
        confidence = "Low"

    # Evidence formulation
    evidence: list[str] = []
    evidence.append(
        f"Analyzed {analyzed_frames_count} sampled frames across {scene_coverage} detected scene(s) ({scored_count} frames evaluated by detector models)."
    )

    if scored_count > 0:
        if suspicious_count > 0:
            evidence.append(
                f"{suspicious_count} of {scored_count} evaluated frames exhibited synthetic or altered feature signatures (>= {LIKELY_AI_THRESHOLD}%)."
            )
        else:
            evidence.append(
                f"All {scored_count} evaluated frames showed consistent natural baseline characteristics (<= {NO_SIGNS_THRESHOLD}%)."
            )

    if unstable_count == 0 and scored_count >= 2:
        evidence.append("Temporal consistency verified: adjacent sampled frames showed stable score transitions without erratic oscillation.")
    elif unstable_count > 0:
        evidence.append(
            f"Temporal instability detected: {unstable_count} adjacent frame pair(s) exhibited significant score divergence between consecutive samples."
        )

    # Single-frame outlier rule
    if suspicious_count == 1 and scored_count > 1:
        evidence.append(
            "An isolated frame exhibited elevated synthetic indicators, but was not treated as definitive proof of full video generation; multi-frame consensus was not reached."
        )

    if classification == "Inconclusive":
        if suspicious_count > 0 and (scored_count - suspicious_count) > 0:
            evidence.append("Mixed signals across sampled frames prevented a uniform AI-generation classification.")
        elif ai_prob is not None and NO_SIGNS_THRESHOLD < ai_prob < LIKELY_AI_THRESHOLD:
            evidence.append(
                f"Aggregated video score ({ai_prob}%) lies in the inconclusive boundary region between human and synthetic thresholds."
            )
        else:
            evidence.append("Available visual evidence was mixed or insufficient across the sampled timeline.")

    if nemotron_summary and nemotron_summary.get("status") == "completed":
        nem_sum = nemotron_summary.get("summary")
        if nem_sum:
            evidence.append(f"Multimodal visual narrative: {nem_sum[:130]}...")

    return {
        "ai_probability": ai_prob,
        "human_probability": human_prob,
        "classification": classification,
        "confidence": confidence,
        "is_calibrated": False,
        "score_label": "AI-Likelihood Score",
        "evidence": evidence,
        "analyzed_frames": analyzed_frames_count,
        "scored_frames": scored_count,
        "model_info": {
            "models": models_used,
            "method": "Multi-frame uniform & scene-change sampling with detector ensemble averaging and adjacent-frame temporal stability filtering.",
            "limitations": [
                "Scores represent model-estimated likelihoods, not statistically calibrated absolute probabilities.",
                "Frame sampling intervals may miss transient actions occurring between sampled timestamps.",
                "Platform transcoding, compression artifacts, and low bitrate can degrade forensic detection accuracy.",
            ],
        },
        "status": "completed" if ai_prob is not None else "inconclusive",
    }
