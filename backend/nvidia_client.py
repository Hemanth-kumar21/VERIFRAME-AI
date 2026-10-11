from __future__ import annotations

import base64
import io
import json
import logging
import re
import time
from typing import Any

import requests
from PIL import Image

from .config import (
    NVIDIA_API_KEY,
    NVIDIA_BASE_URL,
    NVIDIA_MAX_TOKENS,
    NVIDIA_MODEL,
    NVIDIA_REASONING_BUDGET,
)

logger = logging.getLogger(__name__)


class NvidiaApiError(Exception):
    """Custom exception for NVIDIA API failures."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def get_nvidia_status() -> dict[str, Any]:
    """Return non-sensitive configuration status of the NVIDIA Nemotron provider."""
    is_configured = bool(NVIDIA_API_KEY and not NVIDIA_API_KEY.startswith("PASTE_YOUR"))
    return {
        "available": is_configured,
        "status": "configured" if is_configured else "missing_key",
        "model": NVIDIA_MODEL,
        "endpoint": NVIDIA_BASE_URL,
        "message": (
            "NVIDIA Nemotron video reasoning is ready."
            if is_configured
            else "NVIDIA_API_KEY is not set or contains a placeholder. Video forensic checks will proceed without Nemotron."
        ),
    }


def format_frame_data_uri(
    frame_bytes: bytes,
    mime_type: str = "image/jpeg",
    max_dimension: int = 768,
) -> str:
    """Resize image to reasonable limits while preserving aspect ratio and return base64 data URI."""
    try:
        with Image.open(io.BytesIO(frame_bytes)) as img:
            img = img.convert("RGB")
            w, h = img.size
            if max(w, h) > max_dimension:
                scale = max_dimension / max(w, h)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{encoded}"
    except Exception as exc:
        logger.warning("Frame resizing failed (%s); using raw bytes.", exc)
        encoded = base64.b64encode(frame_bytes).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"


def _post_nemotron_request(
    messages: list[dict[str, Any]],
    max_tokens: int | None = None,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Execute a chat completion request to NVIDIA with bounded backoff for transient errors."""
    if not NVIDIA_API_KEY or NVIDIA_API_KEY.startswith("PASTE_YOUR"):
        raise NvidiaApiError("NVIDIA_API_KEY is missing or unconfigured.", status_code=401)

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "model": NVIDIA_MODEL,
        "messages": messages,
        "max_tokens": max_tokens or NVIDIA_MAX_TOKENS,
        "temperature": 0.6,
        "top_p": 0.95,
    }
    if NVIDIA_REASONING_BUDGET > 0:
        payload["reasoning_budget"] = NVIDIA_REASONING_BUDGET

    last_error_msg = ""
    last_status = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Sending request to NVIDIA Nemotron (attempt %d/%d)...", attempt, max_retries)
            resp = requests.post(
                NVIDIA_BASE_URL,
                headers=headers,
                json=payload,
                timeout=45,
            )

            if resp.status_code == 200:
                return resp.json()

            last_status = resp.status_code
            try:
                err_json = resp.json()
                err_detail = err_json.get("error", {}).get("message") or resp.text
            except Exception:
                err_detail = resp.text

            last_error_msg = f"NVIDIA API HTTP {resp.status_code}: {err_detail[:200]}"
            logger.warning("NVIDIA attempt %d returned HTTP %d: %s", attempt, resp.status_code, last_error_msg)

            # Retry only transient 429 or 5xx errors with exponential backoff
            if resp.status_code in (429, 502, 503, 504) and attempt < max_retries:
                backoff = 2 * (2 ** (attempt - 1))
                time.sleep(backoff)
                continue

            # Non-transient errors (400, 401, 403) fail fast
            raise NvidiaApiError(last_error_msg, status_code=resp.status_code)

        except requests.RequestException as req_exc:
            last_error_msg = f"Network connection error: {str(req_exc)}"
            logger.warning("NVIDIA attempt %d connection exception: %s", attempt, last_error_msg)
            if attempt < max_retries:
                time.sleep(2 * attempt)
                continue
            raise NvidiaApiError(last_error_msg) from req_exc

    raise NvidiaApiError(last_error_msg or "Max retries exceeded communicating with NVIDIA.", status_code=last_status)


def analyze_video_nemotron(
    sampled_frames: list[dict[str, Any]],
    video_info: dict[str, Any],
) -> dict[str, Any]:
    """Analyze a chronological sequence of video frames using NVIDIA Nemotron-3-Nano-Omni."""
    if not sampled_frames:
        return {
            "status": "skipped",
            "message": "No sampled frames available for multimodal analysis.",
        }

    # Cap to at most 6 representative frames evenly distributed to fit context/token limits
    if len(sampled_frames) > 6:
        step = len(sampled_frames) / 6
        selected_frames = [sampled_frames[int(i * step)] for i in range(6)]
    else:
        selected_frames = sampled_frames

    content_parts: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "You are an expert AI video analyst. You are examining a chronological sequence of sampled frames "
                f"from a video (Duration: {video_info.get('duration_seconds', 0):.1f}s, "
                f"Resolution: {video_info.get('width', 0)}x{video_info.get('height', 0)}).\n\n"
                "Review each frame and its timestamp carefully. Identify visible subjects, actions, movements, "
                "environmental setting, interactions, and any notable transitions or anomalies.\n\n"
                "You MUST respond with a valid JSON object strictly matching this schema:\n"
                "{\n"
                '  "summary": "Coherent, detailed 2-4 sentence narrative explanation of what happens in the video.",\n'
                '  "scene_descriptions": [\n'
                '    {"scene_id": 1, "start_time": "00:00", "description": "Description of scene"}\n'
                "  ],\n"
                '  "timestamped_events": [\n'
                '    {\n'
                '      "timestamp_seconds": 1.5,\n'
                '      "timestamp_formatted": "00:01",\n'
                '      "description": "What action occurs",\n'
                '      "visible_objects": ["object1", "person"],\n'
                '      "actions": ["walking", "turning"],\n'
                '      "confidence": "high/moderate/tentative"\n'
                "    }\n"
                "  ],\n"
                '  "important_observations": ["Key observation 1", "Key observation 2"],\n'
                '  "limitations": ["Explanation of any uncertainties between sparse frames"]\n'
                "}\n\n"
                "Do NOT wrap the JSON in markdown code fences if possible, or use standard ```json. "
                "Only state facts directly visible in the sampled frames; do not invent unverified names, emotions, or unseen events."
            ),
        }
    ]

    for idx, f in enumerate(selected_frames, 1):
        ts = f.get("timestamp", 0.0)
        formatted_ts = f"{int(ts // 60):02d}:{int(ts % 60):02d}"
        content_parts.append(
            {"type": "text", "text": f"\n--- Frame #{idx} (Timestamp: {formatted_ts} / {ts:.2f}s) ---"}
        )
        data_uri = format_frame_data_uri(f["frame_bytes"])
        content_parts.append({"type": "image_url", "image_url": {"url": data_uri}})

    messages = [{"role": "user", "content": content_parts}]

    try:
        response_json = _post_nemotron_request(messages, max_tokens=NVIDIA_MAX_TOKENS)
        choices = response_json.get("choices", [])
        if not choices:
            raise NvidiaApiError("NVIDIA returned an empty choices list.")

        raw_text = choices[0].get("message", {}).get("content", "").strip()
        parsed_data = _extract_json(raw_text)

        def _ensure_list(val: Any) -> list[str]:
            if isinstance(val, list):
                return [str(x).strip() for x in val if x]
            if isinstance(val, str) and val.strip():
                return [val.strip()]
            return []

        parsed_limitations = _ensure_list(parsed_data.get("limitations"))
        if not parsed_limitations:
            parsed_limitations = [
                "Sparse frame sampling intervals may miss rapid actions occurring between sampled timestamps."
            ]

        # Standardize and validate structured response
        return {
            "status": "completed",
            "model": NVIDIA_MODEL,
            "sampled_frames_used": len(selected_frames),
            "summary": parsed_data.get("summary") or raw_text[:500],
            "scene_descriptions": parsed_data.get("scene_descriptions") if isinstance(parsed_data.get("scene_descriptions"), list) else [],
            "timestamped_events": parsed_data.get("timestamped_events") if isinstance(parsed_data.get("timestamped_events"), list) else [],
            "important_observations": _ensure_list(parsed_data.get("important_observations")),
            "limitations": parsed_limitations,
            "raw_response": raw_text if not parsed_data.get("summary") else None,
        }

    except Exception as exc:
        logger.error("Nemotron video analysis failed: %s", exc)
        return {
            "status": "failed",
            "model": NVIDIA_MODEL,
            "error": str(exc),
            "summary": f"Nemotron video analysis could not be completed ({str(exc)}).",
            "timestamped_events": [],
            "important_observations": [],
            "limitations": ["Multimodal AI service was unavailable at time of request."],
        }


def ask_video_nemotron(
    question: str,
    nemotron_context: dict[str, Any],
    video_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Answer a user question about the video grounded in visual evidence."""
    context_summary = nemotron_context.get("summary", "No summary available.")
    events = nemotron_context.get("timestamped_events", [])
    observations = nemotron_context.get("important_observations", [])

    events_text = "\n".join(
        f"- [{e.get('timestamp_formatted', '00:00')}] {e.get('description', '')} (Actions: {', '.join(e.get('actions', []))})"
        for e in events
    ) or "None recorded."

    obs_text = "\n".join(f"- {o}" for o in observations) or "None recorded."

    system_prompt = (
        "You are an objective AI video forensics assistant powered by NVIDIA Nemotron. "
        "Answer the user's question about the video based STRICTLY on the observed evidence and timestamps below.\n"
        "If the question asks about something not visible in the evidence or between sampled frames, "
        "explicitly state that the visual evidence is insufficient to confirm it.\n"
        "Never invent details or speculate beyond the provided evidence.\n\n"
        f"VIDEO DURATION: {video_info.get('duration_seconds', 0) if video_info else 'Unknown'}s\n"
        f"RECORDED VIDEO SUMMARY:\n{context_summary}\n\n"
        f"TIMESTAMPED EVENTS:\n{events_text}\n\n"
        f"KEY OBSERVATIONS:\n{obs_text}\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question.strip()},
    ]

    try:
        response_json = _post_nemotron_request(messages, max_tokens=1024)
        choice = response_json.get("choices", [{}])[0]
        answer_text = choice.get("message", {}).get("content", "").strip()

        # Extract any mentioned timestamps (e.g. 00:01, 00:04, 1.5s)
        timestamps_found = re.findall(r"\b\d{1,2}:\d{2}\b", answer_text)

        return {
            "status": "success",
            "question": question,
            "answer": answer_text,
            "grounded_timestamps": list(set(timestamps_found)),
            "model": NVIDIA_MODEL,
        }
    except Exception as exc:
        logger.error("Nemotron Q&A failed: %s", exc)
        return {
            "status": "error",
            "question": question,
            "answer": f"Unable to process question ({str(exc)}). Please verify your NVIDIA_API_KEY.",
            "grounded_timestamps": [],
            "model": NVIDIA_MODEL,
        }


def _extract_json(text: str) -> dict[str, Any]:
    """Safely extract JSON object from LLM response text."""
    clean = text.strip()
    # Check for markdown code fence ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, re.DOTALL)
    if match:
        clean = match.group(1)
    else:
        # Check for first { and last }
        start = clean.find("{")
        end = clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            clean = clean[start : end + 1]

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        logger.warning("Could not parse JSON from Nemotron output; using fallback wrapper.")
        return {"summary": text}
