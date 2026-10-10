from __future__ import annotations

import base64
import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI
from PIL import Image

from . import detectors
from .check_llm import check_llm_status
from .config import (
    DETECTOR_C_AI_LABEL,
    DETECTOR_C_MODEL,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    VISION_MODEL,
)
from .explain import build_explanation
from .grounding import review_grounding
from .provenance import check_c2pa, read_metadata
from .quality import assess_quality
from .robustness import run_robustness_checks
from .tiles import run_tile_analysis
from .verdict import evaluate_verdict

SYSTEM_INSTRUCTION = (
    "You are a cautious image-forensics investigator. Use only tool outputs as evidence. "
    "Never invent forensic reasons. Never call a result proof. Never infer visual artifacts "
    "unless a tool reported them. When evidence is insufficient, say so."
)

_TOOL_DESCRIPTIONS = {
    "get_file_info": "Get validated image dimensions, format, and byte size without the user's filename.",
    "read_metadata": "Inspect available image metadata. Missing metadata is not evidence either way.",
    "check_c2pa": "Check C2PA status if c2patool is available.",
    "assess_quality": "Assess image resolution and quality limitations.",
    "run_detector_a": "Run configured image detector A and return its structured status.",
    "run_detector_b": "Run configured image detector B and return its structured status.",
    "run_detector_c": "Run the optional configured third image detector.",
    "run_robustness_checks": "Measure configured detector stability on image variants.",
    "run_tile_analysis": "Run experimental detector tile analysis; it is not proof of editing.",
    "describe_image": "Use the configured vision model to describe visible content only when requested.",
}

ProgressCallback = Callable[[str, str, Any | None], None]


def _emit_progress(
    callback: ProgressCallback | None,
    step: str,
    status: str,
    result: Any | None = None,
) -> None:
    if callback:
        callback(step, status, result)


def _client() -> OpenAI:
    if not LLM_API_KEY or not LLM_BASE_URL:
        raise RuntimeError("LLM provider configuration is incomplete.")
    return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=30)


def _get_file_info(image_path: str) -> dict[str, Any]:
    with Image.open(image_path) as image:
        width, height = image.size
        image_format = image.format
    return {
        "format": image_format,
        "width": width,
        "height": height,
        "size_bytes": Path(image_path).stat().st_size,
    }


def _describe_image(image_path: str, client: OpenAI) -> dict[str, Any]:
    if not VISION_MODEL:
        return {"status": "not_configured", "message": "VISION_MODEL is not configured."}
    mime_type = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
    encoded_image = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Describe only directly visible image content. Do not infer whether it is AI-generated, "
                    "edited, authentic, or manipulated."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the visible content briefly."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"},
                    },
                ],
            },
        ],
    )
    description = response.choices[0].message.content or ""
    return {"status": "ok", "description": description[:1200], "model": VISION_MODEL}


def _tools_for_image(image_path: str, client: OpenAI) -> dict[str, Any]:
    tools = {
        "get_file_info": lambda: _get_file_info(image_path),
        "read_metadata": lambda: read_metadata(image_path),
        "check_c2pa": lambda: check_c2pa(image_path),
        "assess_quality": lambda: assess_quality(image_path),
        "run_detector_a": lambda: detectors.run_detector_a(image_path),
        "run_detector_b": lambda: detectors.run_detector_b(image_path),
        "run_robustness_checks": lambda: run_robustness_checks(image_path),
        "run_tile_analysis": lambda: run_tile_analysis(image_path),
    }
    if DETECTOR_C_MODEL and DETECTOR_C_AI_LABEL:
        tools["run_detector_c"] = lambda: detectors.run_detector_c(image_path)
    if VISION_MODEL:
        tools["describe_image"] = lambda: _describe_image(image_path, client)
    return tools


def _tool_specs(available_tools: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        }
        for name, description in _TOOL_DESCRIPTIONS.items()
        if name in available_tools
    ]


def _execute_agent_tools(
    image_path: str,
    client: OpenAI,
    progress_callback: ProgressCallback | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], str | None, int]:
    available_tools = _tools_for_image(image_path, client)
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {
            "role": "user",
            "content": (
                "Investigate this image using structured tools. Check image information, metadata, provenance, "
                "quality, both configured detectors, and robustness when those checks are available. Use tiles "
                "only if useful. Do not request the raw image except by explicitly calling describe_image. "
                "When finished, return JSON with evidence_summary, what_was_not_checked, and a plain_explanation "
                "of at most three short sentences."
            ),
        },
    ]
    outputs: dict[str, Any] = {}
    trace = []
    calls = 0

    for _ in range(12):
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=_tool_specs(available_tools),
            tool_choice="auto",
        )
        calls += 1
        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        if not tool_calls:
            return outputs, trace, message.content, calls

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [call.model_dump(exclude_none=True) for call in tool_calls],
            }
        )
        for tool_call in tool_calls:
            name = tool_call.function.name
            started_at = time.perf_counter()
            _emit_progress(progress_callback, name, "running")
            if name not in available_tools:
                result = {"status": "unavailable", "message": "This tool is not enabled."}
            elif name in outputs:
                result = outputs[name]
            else:
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                    if arguments:
                        raise ValueError("Tools do not accept arguments.")
                    result = available_tools[name]()
                except (ValueError, json.JSONDecodeError):
                    result = {"status": "invalid_arguments", "message": "Tool arguments were rejected."}
                except Exception as exc:
                    result = {
                        "status": "error",
                        "message": f"{type(exc).__name__}: tool execution failed.",
                    }
                outputs[name] = result
            trace.append(
                {
                    "step": name,
                    "result": result,
                    "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
                }
            )
            _emit_progress(progress_callback, name, "completed", result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
    return outputs, trace, None, calls


def _run_fixed_pipeline(
    image_path: str,
    client: OpenAI | None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    functions = {
        "get_file_info": lambda: _get_file_info(image_path),
        "read_metadata": lambda: read_metadata(image_path),
        "check_c2pa": lambda: check_c2pa(image_path),
        "assess_quality": lambda: assess_quality(image_path),
        "run_detector_ensemble": lambda: detectors.run_detector_ensemble(image_path),
        "run_robustness_checks": lambda: run_robustness_checks(image_path),
        "run_tile_analysis": lambda: run_tile_analysis(image_path),
    }
    if client and VISION_MODEL:
        functions["describe_image"] = lambda: _describe_image(image_path, client)

    outputs = {}
    trace = []
    for name, function in functions.items():
        started_at = time.perf_counter()
        _emit_progress(progress_callback, name, "running")
        try:
            result = function()
            event_status = "completed"
        except Exception as exc:
            result = {"status": "error", "message": f"{type(exc).__name__}: tool execution failed."}
            event_status = "failed"
        outputs[name] = result
        trace.append(
            {
                "step": name,
                "result": result,
                "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
            }
        )
        _emit_progress(progress_callback, name, event_status, result)
    return outputs, trace


def _derive_verdict(outputs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    detector_ensemble = outputs.get("run_detector_ensemble")
    if isinstance(detector_ensemble, dict):
        detector_results = detector_ensemble.get("detectors", [])
    else:
        detector_results = [
            outputs[name]
            for name in ("run_detector_a", "run_detector_b", "run_detector_c")
            if isinstance(outputs.get(name), dict)
        ]
    scores = [
        result["score"]
        for result in detector_results
        if result.get("status") == "ok" and isinstance(result.get("score"), (int, float))
    ]
    quality = outputs.get("assess_quality", {})
    quality_label = quality.get("quality", "unknown") if isinstance(quality, dict) else "unknown"
    small_image = bool(quality.get("small_image", False)) if isinstance(quality, dict) else False
    robustness = outputs.get("run_robustness_checks", {})
    stability = robustness.get("stability") if isinstance(robustness, dict) else None
    verdict = evaluate_verdict(scores, stability, quality_label, small_image)

    tool_summaries = {
        "file_info": outputs.get("get_file_info", {}),
        "metadata": outputs.get("read_metadata", {}),
        "c2pa": outputs.get("check_c2pa", {}),
        "quality": quality,
        "detectors": detector_results,
        "robustness": robustness,
        "tiles": outputs.get("run_tile_analysis", {}),
    }
    verdict["tool_summaries"] = tool_summaries
    return verdict, tool_summaries


def _parse_plain_explanation(content: str | None) -> str | None:
    if not content:
        return None
    try:
        payload = json.loads(content)
        if isinstance(payload, dict):
            text = payload.get("plain_explanation")
            if isinstance(text, str):
                content = text
    except (ValueError, TypeError):
        pass
    sentences = [sentence.strip() for sentence in content.replace("\n", " ").split(".") if sentence.strip()]
    return ". ".join(sentences[:3]).strip() + ("." if sentences else "")


def _request_explanation(client: OpenAI, evidence: dict[str, Any], draft: str | None = None) -> str | None:
    prompt = {
        "evidence": evidence,
        "previous_draft": draft,
        "instruction": (
            "Write a plain-language explanation in no more than three short sentences. Use only the supplied "
            "structured tool outputs. Never say proof, definitely, authentic, or real. Do not infer visual details."
        ),
    }
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
    )
    return _parse_plain_explanation(response.choices[0].message.content)


def _review_with_llm(client: OpenAI, evidence: dict[str, Any], explanation: str) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Review whether every factual claim in the explanation is directly supported by the "
                    "provided structured tool outputs. Return only JSON: "
                    '{"supported": boolean, "unsupported_claims": [string]}.'
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"tool_outputs": evidence, "explanation": explanation},
                    ensure_ascii=False,
                ),
            },
        ],
    )
    try:
        payload = json.loads(response.choices[0].message.content or "")
        supported = payload.get("supported")
        unsupported = payload.get("unsupported_claims")
        if isinstance(supported, bool) and isinstance(unsupported, list):
            return {
                "supported": supported and not unsupported,
                "unsupported_claims": [str(claim) for claim in unsupported],
            }
    except (ValueError, TypeError, AttributeError):
        pass
    return {"supported": False, "unsupported_claims": ["Grounding reviewer returned invalid JSON."]}


def investigate_video_evidence(
    video_evidence: dict[str, Any],
    verdict: str,
    lang: str,
    provider_status: dict[str, Any] | None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[str, dict[str, Any]]:
    template = build_explanation(verdict, lang=lang, style="simple")
    status = provider_status or {}
    if not status.get("available", False):
        _emit_progress(progress_callback, "video_investigation", "unavailable", {
            "status": status.get("status", "not_configured"),
        })
        _emit_progress(progress_callback, "grounding_review", "unavailable", {
            "reason": "No model-generated explanation was produced.",
        })
        return template, {"status": "unavailable", "llm_calls": 0, "grounded": False}

    _emit_progress(progress_callback, "video_investigation", "running")
    try:
        client = _client()
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Explain a video investigation using only the supplied structured evidence. "
                        "The deterministic verdict is authoritative and must not be changed. Do not "
                        "invent visual artifacts, faces, motion, audio, or causes. Do not say proof, "
                        "definitely, authentic, or real. Return only a concise explanation in the "
                        "requested language."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "deterministic_verdict": verdict,
                            "structured_video_evidence": video_evidence,
                            "language": lang,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        draft = _parse_plain_explanation(response.choices[0].message.content)
        if not draft:
            _emit_progress(progress_callback, "video_investigation", "failed")
            _emit_progress(progress_callback, "grounding_review", "unavailable")
            return template, {"status": "template_fallback", "llm_calls": 1, "grounded": False}

        _emit_progress(progress_callback, "video_investigation", "completed")
        evidence = {
            "deterministic_verdict": verdict,
            "structured_video_evidence": video_evidence,
        }
        _emit_progress(progress_callback, "grounding_review", "running")
        review = _review_with_llm(client, evidence, draft)
        llm_calls = 2
        local_review = review_grounding(evidence, draft)
        if review["supported"] and local_review["supported"]:
            _emit_progress(progress_callback, "grounding_review", "completed", review)
            return draft, {"status": "grounded", "llm_calls": llm_calls, "grounded": True}
        _emit_progress(progress_callback, "grounding_review", "failed", review)
        return template, {
            "status": "template_fallback",
            "llm_calls": llm_calls,
            "grounded": False,
        }
    except Exception as exc:
        _emit_progress(progress_callback, "video_investigation", "failed")
        _emit_progress(progress_callback, "grounding_review", "unavailable")
        return template, {
            "status": "template_fallback",
            "llm_calls": 0,
            "grounded": False,
            "error_type": type(exc).__name__,
        }


def analyze_image(
    image_path: str,
    lang: str = "en",
    provider_status: dict[str, Any] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    started_at = time.perf_counter()
    llm_status = provider_status or check_llm_status()
    use_llm = bool(llm_status.get("available", False))
    client = None
    if use_llm:
        try:
            client = _client()
        except Exception:
            use_llm = False

    mode = "template"
    llm_calls = 0
    outputs: dict[str, Any]
    trace: list[dict[str, Any]]
    model_explanation = None
    if use_llm and client and llm_status.get("tool_calling") == "supported":
        try:
            outputs, trace, content, llm_calls = _execute_agent_tools(
                image_path,
                client,
                progress_callback,
            )
            model_explanation = _parse_plain_explanation(content)
            mode = "agent"
        except Exception:
            outputs, trace = _run_fixed_pipeline(image_path, client, progress_callback)
            mode = "fixed pipeline"
    else:
        outputs, trace = _run_fixed_pipeline(
            image_path,
            client if use_llm else None,
            progress_callback,
        )
        mode = "fixed pipeline" if use_llm else "template"

    verdict, tool_summaries = _derive_verdict(outputs)
    safe_explanation = build_explanation(verdict["verdict"], lang=lang, style="simple")
    if use_llm and client and mode == "fixed pipeline":
        _emit_progress(progress_callback, "write_explanation", "running")
        try:
            model_explanation = _request_explanation(client, tool_summaries)
            llm_calls += 1
        except Exception:
            model_explanation = None
        _emit_progress(progress_callback, "write_explanation", "completed")
    if use_llm and client and mode == "agent" and model_explanation:
        _emit_progress(progress_callback, "review_evidence", "running")
        try:
            review = _review_with_llm(client, tool_summaries, model_explanation)
            llm_calls += 1
            if not review["supported"]:
                model_explanation = _request_explanation(client, tool_summaries, model_explanation)
                llm_calls += 1
                if model_explanation:
                    review = _review_with_llm(client, tool_summaries, model_explanation)
                    llm_calls += 1
            if not model_explanation or not review["supported"]:
                model_explanation = None
        except Exception:
            model_explanation = None
        _emit_progress(progress_callback, "review_evidence", "completed")

    if model_explanation:
        local_review = review_grounding(tool_summaries, model_explanation)
        if local_review["supported"]:
            safe_explanation = model_explanation

    explanations = {
        "en": build_explanation(verdict["verdict"], "en", "simple"),
        "te": build_explanation(verdict["verdict"], "te", "simple"),
        "hi": build_explanation(verdict["verdict"], "hi", "simple"),
    }
    if lang in explanations:
        explanations[lang] = safe_explanation

    what_was_not_checked = []
    if verdict["configured_detector_count"] < 2:
        what_was_not_checked.append("Two configured image-forensics detectors were not available.")
    if not isinstance(tool_summaries.get("c2pa"), dict) or tool_summaries["c2pa"].get("status") == "not verifiable":
        what_was_not_checked.append("C2PA provenance could not be verified.")
    if tool_summaries.get("tiles", {}).get("status") != "ok":
        what_was_not_checked.append("Regional detector analysis was unavailable.")
    if "describe_image" not in outputs:
        what_was_not_checked.append("Vision-model image description was not requested or configured.")

    return {
        "token": None,
        "verdict": verdict["verdict"],
        "evidence_strength": verdict["evidence_strength"],
        "agreement": verdict["agreement"],
        "tool_summaries": tool_summaries,
        "limitations": [
            "This result is an estimate, not proof of authenticity or AI generation.",
            "Compression and forwarding can remove forensic traces.",
            "Missing metadata is not evidence either way.",
            "Regional detector analysis is experimental and not proof of editing.",
        ],
        "trace": trace,
        "explanation": explanations,
        "evidence_summary": tool_summaries,
        "what_was_not_checked": what_was_not_checked,
        "plain_explanation": safe_explanation,
        "mode": mode,
        "llm_provider_info": {
            "base_url": LLM_BASE_URL,
            "model": LLM_MODEL or None,
            "status": llm_status.get("status", "offline"),
            "tool_calling": llm_status.get("tool_calling", "not_checked"),
            "llm_calls": llm_calls,
            "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
        },
    }
