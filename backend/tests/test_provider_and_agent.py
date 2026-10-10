from __future__ import annotations

import io
import json
from types import SimpleNamespace

from PIL import Image
from fastapi.testclient import TestClient

from backend import agent, check_llm, detectors, main


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_llm_check_never_requires_or_prints_an_api_key(monkeypatch, capsys):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "verified-model")
    monkeypatch.setenv("LLM_API_KEY", "secret-test-key")
    monkeypatch.setattr(
        check_llm.httpx,
        "get",
        lambda *args, **kwargs: FakeResponse(401, {}),
    )

    status = check_llm.check_llm_status()
    check_llm.main()
    printed = capsys.readouterr().out

    assert status["status"] == "invalid_key"
    assert "secret-test-key" not in printed
    assert "verified-model" in printed


def test_llm_check_validates_model_and_tool_call(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("LLM_MODEL", "verified-model")
    monkeypatch.setenv("LLM_API_KEY", "secret-test-key")
    observed_headers = []

    def fake_get(url, headers, timeout):
        observed_headers.append(headers)
        return FakeResponse(200, {"data": [{"id": "verified-model"}]})

    def fake_post(url, headers, json, timeout):
        observed_headers.append(headers)
        return FakeResponse(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {"function": {"name": "get_file_info"}},
                            ],
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(check_llm.httpx, "get", fake_get)
    monkeypatch.setattr(check_llm.httpx, "post", fake_post)

    status = check_llm.check_llm_status()

    assert status["available"] is True
    assert status["model_listed"] is True
    assert status["tool_calling"] == "supported"
    assert all(header["Authorization"] == "Bearer secret-test-key" for header in observed_headers)


def test_llm_check_distinguishes_invalid_key_and_unavailable_model(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("LLM_MODEL", "verified-model")
    monkeypatch.setenv("LLM_API_KEY", "not-a-real-key")
    monkeypatch.setattr(
        check_llm.httpx,
        "get",
        lambda *args, **kwargs: FakeResponse(401, {}),
    )
    assert check_llm.check_llm_status()["status"] == "invalid_key"

    monkeypatch.setattr(
        check_llm.httpx,
        "get",
        lambda *args, **kwargs: FakeResponse(200, {"data": [{"id": "different-model"}]}),
    )
    assert check_llm.check_llm_status()["status"] == "model_unavailable"


def test_duplicate_detector_model_ids_are_not_counted_twice(monkeypatch):
    monkeypatch.setattr(detectors, "DETECTOR_A_MODEL", "same-model")
    monkeypatch.setattr(detectors, "DETECTOR_A_AI_LABEL", "ai")
    monkeypatch.setattr(detectors, "DETECTOR_B_MODEL", "same-model")
    monkeypatch.setattr(detectors, "DETECTOR_B_AI_LABEL", "ai")
    monkeypatch.setattr(detectors, "DETECTOR_C_MODEL", "")
    monkeypatch.setattr(detectors, "DETECTOR_C_AI_LABEL", "")
    monkeypatch.setattr(
        detectors,
        "_load_classifier",
        lambda _model: lambda _image, top_k: [{"label": "ai", "score": 0.9}],
    )

    result = detectors.run_detector_ensemble(Image.new("RGB", (8, 8)))
    assert result["status"] == "insufficient_detectors"
    assert result["scores"] == [90.0]
    assert result["detectors"][1]["status"] == "duplicate_model"


def test_offline_investigation_uses_template_and_keeps_uncertainty(tmp_path, monkeypatch):
    path = tmp_path / "sample.png"
    Image.new("RGB", (512, 512), color=(120, 120, 120)).save(path)
    monkeypatch.setattr(agent, "DETECTOR_C_MODEL", "")
    monkeypatch.setattr(agent, "DETECTOR_C_AI_LABEL", "")

    result = agent.analyze_image(
        str(path),
        provider_status={
            "available": False,
            "status": "missing_key",
            "tool_calling": "not_checked",
        },
    )

    assert result["mode"] == "template"
    assert result["verdict"] == "Inconclusive"
    assert result["llm_provider_info"]["llm_calls"] == 0
    assert result["what_was_not_checked"]
    assert "estimate, not proof" in " ".join(result["limitations"])


def test_grounding_uses_only_tool_evidence_and_rejects_unverified_language():
    outputs = {"assess_quality": {"quality": "good"}}
    assert agent.review_grounding(outputs, "This is definitely authentic.")["supported"] is False
    assert agent.review_grounding(outputs, "The image quality check reported good quality.")["supported"] is True


def test_agent_tool_loop_executes_only_registered_zero_argument_tools(tmp_path):
    path = tmp_path / "sample.png"
    Image.new("RGB", (32, 32)).save(path)

    class FakeCall:
        id = "call-1"
        function = SimpleNamespace(name="get_file_info", arguments="{}")

        @staticmethod
        def model_dump(exclude_none=True):
            return {
                "id": "call-1",
                "type": "function",
                "function": {"name": "get_file_info", "arguments": "{}"},
            }

    tool_message = SimpleNamespace(
        content=None,
        tool_calls=[FakeCall()],
    )
    final_message = SimpleNamespace(
        content=json.dumps(
            {
                "evidence_summary": "File metadata was inspected.",
                "what_was_not_checked": ["Detectors were not requested."],
                "plain_explanation": "The evidence is insufficient for a clear result.",
            }
        ),
        tool_calls=[],
    )

    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **_kwargs):
            self.calls += 1
            message = tool_message if self.calls == 1 else final_message
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    completions = FakeCompletions()
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    outputs, trace, content, calls = agent._execute_agent_tools(str(path), client)

    assert calls == 2
    assert outputs["get_file_info"]["format"] == "PNG"
    assert trace[0]["step"] == "get_file_info"
    assert "plain_explanation" in json.loads(content)


def test_share_card_endpoint_returns_generated_png_without_original_image(monkeypatch):
    monkeypatch.setattr(main, "check_llm_status", lambda: {"available": False, "status": "offline"})
    monkeypatch.setattr(
        main,
        "get_result_by_token",
        lambda token: {
            "token": token,
            "verdict": "Inconclusive",
            "explanation": {"en": "The evidence is mixed."},
        },
    )

    with TestClient(main.app) as client:
        response = client.get("/api/result/public-token/share-card.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"] == 'attachment; filename="very-frame-result.png"'
    with Image.open(io.BytesIO(response.content)) as card:
        assert card.size == (1200, 630)


def test_insights_endpoint_requires_server_token(monkeypatch):
    monkeypatch.setattr(main, "check_llm_status", lambda: {"available": False, "status": "offline"})
    monkeypatch.setattr(
        main,
        "get_insights",
        lambda: {
            "total_analyses": 3,
            "verdict_distribution": {"Inconclusive": 3},
            "inconclusive_share": 100,
            "mode_distribution": {"template": 3},
            "average_latency_ms": 12,
            "wrong_result_reports": 0,
        },
    )
    monkeypatch.setattr(main, "INSIGHTS_ACCESS_TOKEN", "")

    with TestClient(main.app) as client:
        disabled = client.get("/api/insights")
        monkeypatch.setattr(main, "INSIGHTS_ACCESS_TOKEN", "owner-token")
        rejected = client.get("/api/insights", headers={"Authorization": "Bearer wrong"})
        accepted = client.get("/api/insights", headers={"Authorization": "Bearer owner-token"})

    assert disabled.status_code == 503
    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["mode_distribution"] == {"template": 3}
