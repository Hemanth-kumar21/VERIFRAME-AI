from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend import main, video_pipeline


VIDEO_INFO = {
    "duration_seconds": 30.0,
    "width": 1280,
    "height": 720,
    "fps": 30.0,
    "video_codec": "h264",
    "bitrate_bps": 1_000_000,
    "frame_count": 900,
    "container": "mov,mp4,m4a,3gp,3g2,mj2",
    "has_audio": True,
    "audio_codec": "aac",
    "audio_authenticity_assessed": False,
}


def _frame(timestamp: float, scene_id: int, signal: str, score: float) -> dict:
    return {
        "timestamp": timestamp,
        "scene_id": scene_id,
        "quality": {"usable": True},
        "signal": signal,
        "mean_score": score,
    }


@pytest.mark.parametrize(
    ("filename", "mime_type", "header", "extension"),
    [
        ("clip.mp4", "video/mp4", b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00", ".mp4"),
        ("clip.mov", "video/quicktime", b"\x00\x00\x00\x18ftypqt  \x00\x00\x00\x00", ".mov"),
        ("clip.webm", "video/webm", b"\x1aE\xdf\xa3\x00\x00\x00\x00", ".webm"),
    ],
)
def test_video_header_checks_extension_mime_and_container(
    filename, mime_type, header, extension
):
    result = video_pipeline.validate_video_header(filename, mime_type, header)
    assert result["extension"] == extension
    assert result["mime_type"] == mime_type


def test_video_header_rejects_mismatches_and_unsupported_extensions():
    with pytest.raises(video_pipeline.VideoAnalysisError, match="MIME type"):
        video_pipeline.validate_video_header(
            "clip.mp4", "video/quicktime", b"\x00\x00\x00\x18ftypisom"
        )
    with pytest.raises(video_pipeline.VideoAnalysisError, match="signature"):
        video_pipeline.validate_video_header("clip.mov", "video/quicktime", b"not a video")
    with pytest.raises(video_pipeline.VideoAnalysisError, match="Unsupported video extension"):
        video_pipeline.validate_video_header("clip.avi", "video/x-msvideo", b"RIFF")


def test_probe_video_returns_actual_stream_metadata(monkeypatch, tmp_path):
    path = tmp_path / "clip.mp4"
    path.touch()
    monkeypatch.setattr(video_pipeline, "_require_ffmpeg", lambda: ("ffmpeg", "ffprobe"))
    payload = {
        "format": {
            "duration": "30.0",
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "bit_rate": "1200000",
        },
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1280,
                "height": 720,
                "avg_frame_rate": "30/1",
                "nb_frames": "900",
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }
    monkeypatch.setattr(
        video_pipeline.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps(payload), stderr=""
        ),
    )

    result = video_pipeline.probe_video(path)

    assert result["duration_seconds"] == 30.0
    assert result["width"] == 1280
    assert result["fps"] == 30.0
    assert result["video_codec"] == "h264"
    assert result["bitrate_bps"] == 1_200_000
    assert result["frame_count"] == 900
    assert result["has_audio"] is True
    assert result["audio_authenticity_assessed"] is False


def test_probe_video_rejects_excessive_duration_and_resolution(monkeypatch, tmp_path):
    path = tmp_path / "clip.mp4"
    path.touch()
    monkeypatch.setattr(video_pipeline, "_require_ffmpeg", lambda: ("ffmpeg", "ffprobe"))
    monkeypatch.setattr(video_pipeline, "VIDEO_MAX_DURATION_SECONDS", 20)
    payload = {
        "format": {"duration": "30", "format_name": "mov,mp4"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1280,
                "height": 720,
                "avg_frame_rate": "30/1",
            }
        ],
    }
    monkeypatch.setattr(
        video_pipeline.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps(payload), stderr=""
        ),
    )
    with pytest.raises(video_pipeline.VideoAnalysisError, match="duration limit"):
        video_pipeline.probe_video(path)


def test_frame_sampling_spans_video_and_respects_budget(monkeypatch):
    monkeypatch.setattr(video_pipeline, "FRAME_SAMPLE_INTERVAL_SECONDS", 1)
    result = video_pipeline.choose_sample_timestamps(
        duration=60,
        scene_changes=list(range(2, 60, 2)),
        max_frames=8,
    )

    assert len(result) <= 8
    assert result == sorted(result)
    assert result[0] < 10
    assert result[-1] > 50


def test_video_verdict_needs_distributed_suspicious_frames_and_scene_coverage():
    sparse = [
        _frame(1, 1, "suspicious", 92),
        _frame(5, 1, "no_ai_signs", 10),
        _frame(10, 2, "no_ai_signs", 11),
        _frame(15, 2, "no_ai_signs", 12),
    ]
    distributed = [
        _frame(1, 1, "suspicious", 90),
        _frame(5, 1, "suspicious", 91),
        _frame(10, 2, "suspicious", 92),
        _frame(15, 2, "suspicious", 91),
    ]

    assert video_pipeline.aggregate_video_evidence(sparse, 2, VIDEO_INFO)["verdict"] == "Inconclusive"
    assert video_pipeline.aggregate_video_evidence(distributed, 2, VIDEO_INFO)["verdict"] == "Likely AI"


def test_video_without_sufficient_detector_evidence_is_inconclusive():
    frames = [
        _frame(index * 3, index // 2, "insufficient_detectors", None)
        for index in range(1, 6)
    ]
    result = video_pipeline.aggregate_video_evidence(frames, 3, VIDEO_INFO)
    assert result["verdict"] == "Inconclusive"
    assert result["face_tracking"]["status"] == "unavailable"
    assert result["audio_authenticity_assessed"] is False


def test_video_analysis_deletes_all_extracted_frame_files(monkeypatch, tmp_path):
    monkeypatch.setattr(video_pipeline, "probe_video", lambda *_args: VIDEO_INFO)
    monkeypatch.setattr(video_pipeline, "detect_scene_changes", lambda *_args: [10, 20])
    extracted_paths: list[Path] = []

    def extract(_video_path, _timestamp, output_path, _deadline):
        Image.new("RGB", (320, 240), "gray").save(output_path, format="JPEG")
        extracted_paths.append(output_path)

    monkeypatch.setattr(video_pipeline, "_extract_frame", extract)
    monkeypatch.setattr(
        video_pipeline,
        "assess_frame_quality",
        lambda _path: {"usable": True, "limitations": []},
    )
    monkeypatch.setattr(
        video_pipeline.detectors,
        "run_detector_ensemble",
        lambda _path: {
            "status": "ok",
            "detectors": [
                {"status": "ok", "score": 90.0},
                {"status": "ok", "score": 92.0},
            ],
        },
    )

    events = []
    result = video_pipeline.analyze_video(
        tmp_path / "staged.mp4",
        progress_callback=lambda step, status, payload=None: events.append(
            (step, status, payload)
        ),
    )

    assert len(result["frames"]) <= video_pipeline.MAX_ANALYZED_FRAMES
    assert result["analyzed_frame_count"] == len(result["frames"])
    assert result["verdict"] == "Likely AI"
    assert not any(path.exists() for path in extracted_paths)
    assert any(step == "get_video_info" and status == "completed" for step, status, _ in events)
    assert any(step == "run_temporal_checks" for step, _, _ in events)


def test_video_api_reports_ffmpeg_requirement_when_tools_are_missing(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _name: None)
    with TestClient(main.app) as client:
        config = client.get("/api/video/config")
        response = client.post(
            "/api/video/analyze",
            files={
                "file": (
                    "clip.mp4",
                    b"\x00\x00\x00\x18ftypisom",
                    "video/mp4",
                )
            },
        )

    assert config.status_code == 200
    assert config.json()["available"] is False
    assert "FFmpeg and ffprobe" in config.json()["message"]
    assert response.status_code == 503
    assert "FFmpeg and ffprobe" in response.json()["detail"]


def test_video_api_persists_summary_and_cleans_staged_video(monkeypatch):
    saved: dict[str, dict] = {}
    staged_paths: list[Path] = []
    monkeypatch.setattr(main.shutil, "which", lambda _name: "configured-tool")
    monkeypatch.setattr(main, "check_llm_status", lambda: {"available": False, "status": "offline"})

    def fake_analyze_video(video_path, progress_callback=None):
        staged_paths.append(Path(video_path))
        progress_callback("get_video_info", "completed", VIDEO_INFO)
        return {
            "verdict": "Inconclusive",
            "evidence_strength": "Weak",
            "agreement": "Low",
            "limitations": ["estimate, not proof"],
            "frames": [],
            "video_info": VIDEO_INFO,
        }

    monkeypatch.setattr(main, "analyze_video", fake_analyze_video)
    monkeypatch.setattr(main, "save_result", lambda payload: saved.update({payload["token"]: payload}))
    monkeypatch.setattr(main, "get_result_by_token", lambda token: saved.get(token))

    with TestClient(main.app) as client:
        response = client.post(
            "/api/video/analyze",
            files={
                "file": (
                    "clip.mp4",
                    b"\x00\x00\x00\x18ftypisom" + b"test video bytes",
                    "video/mp4",
                )
            },
        )
        token = response.json()["token"]
        events = client.get(f"/api/video/analyze/{token}/events")
        result = client.get(f"/api/video/result/{token}")

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert "get_video_info" in events.text
    assert result.status_code == 200
    assert "video" in result.json()["tool_summaries"]
    assert staged_paths and not staged_paths[0].exists()
