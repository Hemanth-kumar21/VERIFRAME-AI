from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.nvidia_client import (
    format_frame_data_uri,
    get_nvidia_status,
    analyze_video_nemotron,
    ask_video_nemotron,
)
from backend.db import save_result

client = TestClient(app)


def test_get_nvidia_status():
    status = get_nvidia_status()
    assert "available" in status
    assert "model" in status
    assert "endpoint" in status
    assert "status" in status
    assert "key" not in status  # API key must never be exposed


def test_format_frame_data_uri():
    # 1x1 black pixel PNG
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02"
        b"\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    uri = format_frame_data_uri(png_bytes)
    assert uri.startswith("data:image/jpeg;base64,")


def test_analyze_video_nemotron_skipped_on_empty():
    res = analyze_video_nemotron([], {})
    assert res["status"] == "skipped"


@patch("backend.nvidia_client._post_nemotron_request")
def test_analyze_video_nemotron_mocked(mock_post):
    mock_post.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{\n'
                        '  "summary": "A person walks across a park and sits on a bench.",\n'
                        '  "scene_descriptions": [{"scene_id": 1, "start_time": "00:00", "description": "Park pathway"}],\n'
                        '  "timestamped_events": [\n'
                        '    {"timestamp_seconds": 1.0, "timestamp_formatted": "00:01", "description": "Subject enters", "visible_objects": ["person", "path"], "actions": ["walking"], "confidence": "high"}\n'
                        '  ],\n'
                        '  "important_observations": ["Clear daytime lighting"],\n'
                        '  "limitations": ["Brief clip"]\n'
                        '}'
                    )
                }
            }
        ]
    }
    dummy_frames = [{"timestamp": 1.0, "frame_index": 30, "frame_bytes": b"fake_bytes"}]
    res = analyze_video_nemotron(dummy_frames, {"duration_seconds": 5.0, "width": 1280, "height": 720})

    assert res["status"] == "completed"
    assert "bench" in res["summary"]
    assert len(res["timestamped_events"]) == 1
    assert res["timestamped_events"][0]["timestamp_formatted"] == "00:01"


@patch("backend.nvidia_client._post_nemotron_request")
def test_ask_video_nemotron_mocked(mock_post):
    mock_post.return_value = {
        "choices": [
            {"message": {"content": "At 00:01, a person is seen walking towards a bench."}}
        ]
    }
    context = {
        "summary": "Walking in a park.",
        "timestamped_events": [{"timestamp_formatted": "00:01", "description": "Person walking"}],
        "important_observations": [],
    }
    ans = ask_video_nemotron("What happens at 00:01?", context)
    assert ans["status"] == "success"
    assert "bench" in ans["answer"]
    assert "00:01" in ans["grounded_timestamps"]


def test_api_nvidia_status_endpoint():
    resp = client.get("/api/nvidia/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "available" in data
    assert "model" in data


def test_api_video_ask_endpoint():
    dummy_token = "vid_test_token_ask_99"
    save_result({
        "token": dummy_token,
        "verdict": "No AI signs found",
        "evidence_strength": "strong",
        "agreement": "high",
        "tool_summaries": {
            "video": {"video_info": {"duration_seconds": 4.0}},
            "nemotron": {
                "summary": "A robotic arm rotates 180 degrees.",
                "timestamped_events": [
                    {"timestamp_formatted": "00:02", "description": "Robotic arm finishes rotation"}
                ],
                "important_observations": [],
            },
        },
        "mode": "video fixed pipeline",
    })

    with patch("backend.nvidia_client._post_nemotron_request") as mock_post:
        mock_post.return_value = {
            "choices": [{"message": {"content": "The robotic arm completes rotation around 00:02."}}]
        }
        resp = client.post(
            f"/api/video/{dummy_token}/ask",
            json={"question": "What does the robotic arm do?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == dummy_token
        assert "robotic arm" in data["answer"].lower()
