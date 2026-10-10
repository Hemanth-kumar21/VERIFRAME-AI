from __future__ import annotations

import io

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend import detectors, main, quality, robustness, validation
from backend.verdict import evaluate_verdict


def make_image(size=(512, 512), color=(127, 127, 127), fmt="PNG"):
    image = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("fmt", "filename", "mime_type"),
    [
        ("PNG", "test.png", "image/png"),
        ("JPEG", "test.jpg", "image/jpeg"),
        ("JPEG", "test.jpeg", "image/jpeg"),
        ("WEBP", "test.webp", "image/webp"),
    ],
)
def test_validation_accepts_supported_image_types(fmt, filename, mime_type):
    image_data = make_image(fmt=fmt)
    result = validation.validate_image_stream(io.BytesIO(image_data), filename, mime_type)
    assert result["valid"] is True
    assert result["format"] == fmt
    assert result["width"] == 512
    assert result["height"] == 512


def test_validation_rejects_extension_mime_and_magic_mismatches():
    png = make_image()
    with pytest.raises(ValueError, match="do not match"):
        validation.validate_image_stream(io.BytesIO(png), "test.jpg", "image/jpeg")
    with pytest.raises(ValueError, match="MIME"):
        validation.validate_image_stream(io.BytesIO(png), "test.png", "application/octet-stream")
    with pytest.raises(ValueError, match="corrupt"):
        validation.validate_image_stream(
            io.BytesIO(b"\x89PNG\r\n\x1a\nnot-a-valid-image"),
            "broken.png",
            "image/png",
        )


def test_validation_caps_read_size(monkeypatch):
    monkeypatch.setattr(validation, "MAX_IMAGE_BYTES", 8)

    class BoundedReader:
        read_size = None

        def read(self, size=-1):
            self.read_size = size
            return b"x" * size

    reader = BoundedReader()
    with pytest.raises(ValueError, match="limit"):
        validation.validate_image_stream(reader, "oversized.png", "image/png")
    assert reader.read_size == 9


def test_validation_rejects_decompression_bomb(monkeypatch):
    monkeypatch.setattr(validation, "MAX_IMAGE_PIXELS", 100)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    image_data = make_image(size=(11, 10))
    with pytest.raises(ValueError, match="decompression bomb|pixel count"):
        validation.validate_image_stream(io.BytesIO(image_data), "large.png", "image/png")


def test_unconfigured_models_do_not_create_detector_scores(monkeypatch):
    monkeypatch.setattr(detectors, "DETECTOR_A_MODEL", "")
    monkeypatch.setattr(detectors, "DETECTOR_A_AI_LABEL", "")
    monkeypatch.setattr(detectors, "DETECTOR_B_MODEL", "")
    monkeypatch.setattr(detectors, "DETECTOR_B_AI_LABEL", "")
    monkeypatch.setattr(detectors, "DETECTOR_C_MODEL", "")
    monkeypatch.setattr(detectors, "DETECTOR_C_AI_LABEL", "")

    result = detectors.run_detector_ensemble(Image.new("RGB", (8, 8)))
    assert result["status"] == "insufficient_detectors"
    assert result["scores"] == []
    assert result["average"] is None
    assert all(item["status"] == "not_configured" for item in result["detectors"])


def test_configured_detectors_return_only_model_class_scores(monkeypatch):
    monkeypatch.setattr(detectors, "DETECTOR_A_MODEL", "configured-model-a")
    monkeypatch.setattr(detectors, "DETECTOR_A_AI_LABEL", "ai-generated")
    monkeypatch.setattr(detectors, "DETECTOR_B_MODEL", "configured-model-b")
    monkeypatch.setattr(detectors, "DETECTOR_B_AI_LABEL", "synthetic")
    monkeypatch.setattr(detectors, "DETECTOR_C_MODEL", "")
    monkeypatch.setattr(detectors, "DETECTOR_C_AI_LABEL", "")
    monkeypatch.setattr(
        detectors,
        "_load_classifier",
        lambda model_id: (
            lambda image, top_k: [
                {
                    "label": "ai-generated" if model_id.endswith("a") else "synthetic",
                    "score": 0.91 if model_id.endswith("a") else 0.84,
                },
                {"label": "real", "score": 0.09 if model_id.endswith("a") else 0.16},
            ]
        ),
    )

    result = detectors.run_detector_ensemble(Image.new("RGB", (16, 16)))
    assert result["status"] == "ok"
    assert result["scores"] == [91.0, 84.0]
    assert result["average"] == 87.5
    assert all(item["status"] == "ok" for item in result["detectors"])


def test_quality_reports_low_resolution_and_recommendation(tmp_path):
    path = tmp_path / "small.png"
    path.write_bytes(make_image(size=(100, 100)))
    result = quality.assess_quality(str(path))
    assert result["quality"] == "low"
    assert result["small_image"] is True
    assert result["recommendation"]
    assert result["warnings"]


def test_robustness_runs_real_variants_and_detects_instability(tmp_path, monkeypatch):
    path = tmp_path / "variant.png"
    path.write_bytes(make_image(size=(512, 512)))
    scores = iter([10.0, 90.0, 10.0, 90.0, 10.0])

    def fake_ensemble(_image):
        return {
            "detectors": [
                {"detector": "test", "status": "ok", "score": next(scores)},
            ],
        }

    monkeypatch.setattr(robustness, "run_detector_ensemble", fake_ensemble)
    result = robustness.run_robustness_checks(str(path))
    assert set(result["variants"]) == {
        "original",
        "resized",
        "center_crop",
        "jpeg_recompressed",
        "horizontal_flip",
    }
    assert result["status"] == "ok"
    assert result["stability"] < 0.75


@pytest.mark.parametrize(
    ("scores", "stability", "quality", "small", "expected"),
    [
        ([], None, "good", False, "Inconclusive"),
        ([95], 0.99, "good", False, "Inconclusive"),
        ([90, 10], 0.99, "good", False, "Inconclusive"),
        ([90, 91], 0.40, "good", False, "Inconclusive"),
        ([90, 91], 0.99, "low", False, "Inconclusive"),
        ([90, 91], 0.99, "good", True, "Inconclusive"),
        ([90, 92], 0.99, "good", False, "Likely AI"),
        ([12, 15], 0.99, "good", False, "No AI signs found"),
    ],
)
def test_verdict_requires_two_agreeing_stable_detectors(
    scores, stability, quality, small, expected
):
    result = evaluate_verdict(scores, stability, quality, small)
    assert result["verdict"] == expected
    if expected == "Inconclusive" and (not scores or len(scores) < 2):
        assert result["evidence_strength"] == "Weak"


def test_analyze_endpoint_removes_temporary_file(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "check_llm_status", lambda: {"available": False, "status": "offline"})
    monkeypatch.setattr(main, "save_result", lambda _result: {"id": 1})

    def fake_analyze(path, lang="en", provider_status=None, progress_callback=None):
        captured["path"] = path
        with Image.open(path) as image:
            assert image.size == (512, 512)
        assert provider_status["available"] is False
        progress_callback("assess_quality", "running")
        progress_callback("assess_quality", "completed", {"quality": "good"})
        return {
            "verdict": "Inconclusive",
            "agreement": "Low",
            "evidence_strength": "Weak",
            "tool_summaries": {},
            "trace": [],
        }

    monkeypatch.setattr(main, "analyze_image", fake_analyze)
    main.REQUEST_BUCKET.clear()
    main.ANALYSIS_JOBS.clear()
    with TestClient(main.app) as client:
        response = client.post(
            "/api/analyze",
            files={"file": ("upload.png", make_image(), "image/png")},
        )
        events = client.get(f"/api/analyze/{response.json()['token']}/events")

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert "assess_quality" in events.text
    assert "completed" in events.text
    assert not __import__("pathlib").Path(captured["path"]).exists()
