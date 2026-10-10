import pytest
from backend.ai_score import (
    compute_image_ai_detection_score,
    compute_video_ai_detection_score,
)


def test_image_ai_detection_score_likely_ai():
    verdict_data = {
        "verdict": "Likely AI",
        "evidence_strength": "Strong",
        "agreement": "High",
        "mean_score": 88.5,
        "spread": 6.0,
        "configured_detector_count": 2,
    }
    tool_summaries = {
        "detectors": [
            {"detector": "detector_a", "model": "demo-edge", "score": 90.0, "status": "ok"},
            {"detector": "detector_b", "model": "demo-entropy", "score": 87.0, "status": "ok"},
        ],
        "quality": {"quality": "high", "width": 1024, "height": 768},
        "robustness": {"stability": 0.94},
    }

    res = compute_image_ai_detection_score(verdict_data, tool_summaries)
    assert res["ai_probability"] == 88.5
    assert res["human_probability"] == 11.5
    assert round(res["ai_probability"] + res["human_probability"], 1) == 100.0
    assert res["classification"] == "Likely AI-Generated"
    assert res["confidence"] == "High"
    assert res["analyzed_frames"] == 1
    assert len(res["evidence"]) >= 3
    assert not res["is_calibrated"]
    assert "AI-Likelihood" in res["score_label"]


def test_image_ai_detection_score_human():
    verdict_data = {
        "verdict": "No AI signs found",
        "evidence_strength": "Moderate",
        "agreement": "High",
        "mean_score": 14.2,
        "spread": 4.0,
        "configured_detector_count": 2,
    }
    tool_summaries = {
        "detectors": [
            {"detector": "detector_a", "model": "demo-edge", "score": 15.0, "status": "ok"},
            {"detector": "detector_b", "model": "demo-entropy", "score": 13.4, "status": "ok"},
        ],
        "quality": {"quality": "high", "width": 800, "height": 600},
    }

    res = compute_image_ai_detection_score(verdict_data, tool_summaries)
    assert res["ai_probability"] == 14.2
    assert res["human_probability"] == 85.8
    assert res["classification"] == "Likely Human-Created"
    assert res["confidence"] == "Medium"


def test_image_ai_detection_score_inconclusive():
    verdict_data = {
        "verdict": "Inconclusive",
        "evidence_strength": "Weak",
        "agreement": "Low",
        "mean_score": 52.0,
        "spread": 35.0,
        "configured_detector_count": 2,
    }
    tool_summaries = {
        "detectors": [],
        "quality": {"quality": "low", "width": 120, "height": 90},
    }

    res = compute_image_ai_detection_score(verdict_data, tool_summaries)
    assert res["classification"] == "Inconclusive"
    assert res["confidence"] == "Low"


def test_video_ai_detection_score_multi_frame():
    video_result = {
        "verdict": "Likely AI",
        "evidence_strength": "Strong",
        "analyzed_frame_count": 8,
        "scored_frame_count": 6,
        "suspicious_signal_count": 5,
        "scene_coverage_count": 2,
        "temporal_checks": {
            "unstable_neighbor_pairs": [],
        },
        "frames": [
            {"timestamp": 0.5, "mean_score": 82.0},
            {"timestamp": 1.5, "mean_score": 84.0},
            {"timestamp": 2.5, "mean_score": 80.0},
            {"timestamp": 3.5, "mean_score": 86.0},
            {"timestamp": 4.5, "mean_score": 85.0},
            {"timestamp": 5.5, "mean_score": 83.0},
        ],
    }

    res = compute_video_ai_detection_score(video_result)
    assert res["classification"] == "Likely AI-Generated"
    assert res["ai_probability"] == 83.3
    assert res["human_probability"] == 16.7
    assert round(res["ai_probability"] + res["human_probability"], 1) == 100.0
    assert res["confidence"] == "High"
    assert res["analyzed_frames"] == 8
    assert res["scored_frames"] == 6
    assert any("Analyzed 8 sampled frames" in ev for ev in res["evidence"])
    assert any("Temporal consistency verified" in ev for ev in res["evidence"])


def test_video_single_suspicious_frame_does_not_force_likely_ai():
    # Only 1 suspicious frame out of 5 frames
    video_result = {
        "verdict": "Inconclusive",
        "evidence_strength": "Moderate",
        "analyzed_frame_count": 5,
        "scored_frame_count": 5,
        "suspicious_signal_count": 1,
        "scene_coverage_count": 2,
        "temporal_checks": {
            "unstable_neighbor_pairs": [{"delta": 45.0}],
        },
        "frames": [
            {"timestamp": 0.0, "mean_score": 20.0},
            {"timestamp": 1.0, "mean_score": 85.0},  # Single outlier
            {"timestamp": 2.0, "mean_score": 22.0},
            {"timestamp": 3.0, "mean_score": 18.0},
            {"timestamp": 4.0, "mean_score": 19.0},
        ],
    }

    res = compute_video_ai_detection_score(video_result)
    assert res["classification"] == "Inconclusive"
    assert res["confidence"] == "Low"
    assert any("isolated frame" in ev.lower() for ev in res["evidence"])
