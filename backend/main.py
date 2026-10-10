from __future__ import annotations

import io
import json
import logging
import secrets
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .config import (
    INSIGHTS_ACCESS_TOKEN,
    MAX_ANALYZED_FRAMES,
    MAX_IMAGE_BYTES,
    VIDEO_ANALYSIS_TIMEOUT_SECONDS,
    VIDEO_MAX_DURATION_SECONDS,
    VIDEO_MAX_FPS,
    VIDEO_MAX_RESOLUTION_HEIGHT,
    VIDEO_MAX_RESOLUTION_WIDTH,
    VIDEO_MAX_SIZE_BYTES,
    VIDEO_MAX_SIZE_MB,
)
from .agent import analyze_image, investigate_video_evidence
from .check_llm import check_llm_status
from .correlation import correlate_case_evidence
from .db import (
    add_case_note,
    attach_item_to_case,
    create_case,
    get_case,
    get_case_audit_logs,
    get_case_items,
    get_insights,
    get_result_by_token,
    list_cases,
    remove_item_from_case,
    save_report,
    save_result,
    update_case,
)
from .explain import build_explanation
from .integrity import generate_forensic_integrity_record
from .nvidia_client import analyze_video_nemotron, ask_video_nemotron, get_nvidia_status
from .report_generator import render_case_report_html, render_single_dossier_html
from .share_card import create_share_card
from .validation import validate_image_stream
from .video_pipeline import VideoAnalysisError, analyze_video, validate_video_header

logger = logging.getLogger(__name__)
JOB_TTL_SECONDS = 60 * 60


class AnalysisJob:
    def __init__(self) -> None:
        self.created_at = time.time()
        self.events: list[dict[str, Any]] = []
        self.completed = False
        self.condition = threading.Condition()

    def publish(self, event: dict[str, Any]) -> None:
        with self.condition:
            self.events.append(event)
            self.condition.notify_all()

    def finish(self) -> None:
        with self.condition:
            self.completed = True
            self.condition.notify_all()


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Very Frame AI")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
REQUEST_BUCKET = {}
VIDEO_REQUEST_BUCKET = {}
ANALYSIS_JOBS: dict[str, AnalysisJob] = {}
ANALYSIS_JOBS_LOCK = threading.Lock()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; script-src 'self' 'unsafe-inline'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.on_event("startup")
async def startup_event() -> None:
    app.state.llm_status = check_llm_status()


@app.get("/health")
async def health() -> dict[str, Any]:
    llm_status = getattr(app.state, "llm_status", None)
    if llm_status is None:
        llm_status = check_llm_status()
    return {
        "status": "ok",
        "llm": "offline" if not llm_status.get("available", False) else "online",
        "message": "AI investigator offline" if not llm_status.get("available", False) else "AI investigator online",
        "provider": llm_status,
    }


@app.post("/api/analyze")
async def analyze(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    lang: str = "en",
) -> dict[str, Any]:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = REQUEST_BUCKET.setdefault(ip, [])
    window[:] = [ts for ts in window if now - ts < 60]
    if len(window) >= 10:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
    window.append(now)

    try:
        contents = await file.read(MAX_IMAGE_BYTES + 1)
        validated_file = validate_image_stream(
            io.BytesIO(contents),
            file.filename or "upload",
            mime_type=file.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = secrets.token_urlsafe(16)
    job = AnalysisJob()
    job.publish(
        {
            "step": "validate_input",
            "status": "completed",
            "result": {
                "format": validated_file["format"],
                "size_bytes": validated_file["size_bytes"],
                "width": validated_file["width"],
                "height": validated_file["height"],
            },
        }
    )
    with ANALYSIS_JOBS_LOCK:
        expired_ids = [
            job_id
            for job_id, existing_job in ANALYSIS_JOBS.items()
            if existing_job.completed and time.time() - existing_job.created_at > JOB_TTL_SECONDS
        ]
        for expired_id in expired_ids:
            del ANALYSIS_JOBS[expired_id]
        ANALYSIS_JOBS[token] = job

    background_tasks.add_task(
        _process_analysis_job,
        token,
        job,
        contents,
        validated_file["format"],
        lang,
        getattr(app.state, "llm_status", None),
    )
    return {"job_id": token, "token": token, "status": "accepted"}


def _is_ffmpeg_available() -> bool:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return True
    if ffmpeg and not ffprobe:
        return True
    return False


@app.get("/api/video/config")
async def video_config() -> dict[str, Any]:
    ffmpeg_available = _is_ffmpeg_available()
    return {
        "available": ffmpeg_available,
        "formats": ["MP4", "MOV", "WebM"] if ffmpeg_available else [],
        "max_size_mb": VIDEO_MAX_SIZE_MB,
        "max_duration_seconds": VIDEO_MAX_DURATION_SECONDS,
        "max_resolution": f"{VIDEO_MAX_RESOLUTION_WIDTH}x{VIDEO_MAX_RESOLUTION_HEIGHT}",
        "max_fps": VIDEO_MAX_FPS,
        "max_analyzed_frames": MAX_ANALYZED_FRAMES,
        "analysis_timeout_seconds": VIDEO_ANALYSIS_TIMEOUT_SECONDS,
        "message": (
            "FFmpeg and ffprobe are ready. Codec support is checked when the video is analyzed."
            if ffmpeg_available
            else "Video analysis requires FFmpeg and ffprobe on the backend PATH."
        ),
    }


@app.post("/api/video/analyze")
async def analyze_video_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    lang: str = "en",
) -> dict[str, str]:
    if lang not in {"en", "te", "hi"}:
        raise HTTPException(status_code=400, detail="Unsupported explanation language.")
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = VIDEO_REQUEST_BUCKET.setdefault(ip, [])
    window[:] = [timestamp for timestamp in window if now - timestamp < 60]
    if len(window) >= 10:
        raise HTTPException(status_code=429, detail="Video request rate limit exceeded. Try again in a minute.")
    window.append(now)
    ffmpeg_available = _is_ffmpeg_available()
    if not ffmpeg_available:
        raise HTTPException(
            status_code=503,
            detail="Video analysis requires FFmpeg and ffprobe on the backend PATH.",
        )


    try:
        header = await file.read(64)
        validate_video_header(file.filename or "video", file.content_type, header)
    except VideoAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = secrets.token_urlsafe(16)
    temp_path: Path | None = None
    total_bytes = 0
    try:
        suffix = Path(file.filename or "video").suffix.lower()
        with tempfile.NamedTemporaryFile(
            prefix="veriframe_video_",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(header)
            total_bytes = len(header)
            if total_bytes > VIDEO_MAX_SIZE_BYTES:
                raise VideoAnalysisError(
                    f"Video exceeds the {VIDEO_MAX_SIZE_MB} MB size limit."
                )
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > VIDEO_MAX_SIZE_BYTES:
                    raise VideoAnalysisError(
                        f"Video exceeds the {VIDEO_MAX_SIZE_MB} MB size limit."
                    )
                temp_file.write(chunk)

        token = secrets.token_urlsafe(16)
        job = AnalysisJob()
        job.publish(
            {
                "step": "validate_video",
                "status": "completed",
                "result": {"container_signature": "matched", "size_bytes": total_bytes},
            }
        )
        with ANALYSIS_JOBS_LOCK:
            expired_ids = [
                job_id
                for job_id, existing_job in ANALYSIS_JOBS.items()
                if existing_job.completed and time.time() - existing_job.created_at > JOB_TTL_SECONDS
            ]
            for expired_id in expired_ids:
                del ANALYSIS_JOBS[expired_id]
            ANALYSIS_JOBS[token] = job

        background_tasks.add_task(
            _process_video_job,
            token,
            job,
            temp_path,
            lang,
            getattr(app.state, "llm_status", None),
        )
        temp_path = None
        return {"job_id": token, "token": token, "status": "accepted"}
    except VideoAnalysisError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="The uploaded video could not be staged safely.") from exc
    finally:
        await file.close()
        if temp_path and temp_path.exists():
            temp_path.unlink()


def _process_video_job(
    job_id: str,
    job: AnalysisJob,
    video_path: Path,
    lang: str,
    provider_status: dict[str, Any] | None,
) -> None:
    try:
        job.publish({"step": "investigation", "status": "running"})
        progress_cb = lambda step, status, payload=None: job.publish(
            {
                "step": step,
                "status": status,
                **({"result": payload} if payload is not None else {}),
            }
        )
        try:
            video_result = analyze_video(
                video_path,
                progress_callback=progress_cb,
                return_sampled_images=True,
            )
        except TypeError:
            video_result = analyze_video(
                video_path,
                progress_callback=progress_cb,
            )
        sampled_images = video_result.pop("_sampled_images", [])
        nemotron_summary: dict[str, Any] = {}
        if sampled_images:
            job.publish({"step": "nemotron_video_understanding", "status": "running"})
            try:
                nemotron_summary = analyze_video_nemotron(
                    sampled_images,
                    video_result.get("video_info", {}),
                )
                events_count = len(nemotron_summary.get("timestamped_events", []))
                job.publish(
                    {
                        "step": "nemotron_video_understanding",
                        "status": "completed",
                        "result": {
                            "summary": nemotron_summary.get("summary", "")[:120],
                            "events_count": events_count,
                        },
                    }
                )
            except Exception as nem_exc:
                logger.warning("Nemotron video analysis failed (%s).", nem_exc)
                job.publish(
                    {
                        "step": "nemotron_video_understanding",
                        "status": "unavailable",
                        "result": str(nem_exc),
                    }
                )

        verdict = video_result["verdict"]
        explanation, investigator_status = investigate_video_evidence(
            video_result,
            verdict,
            lang,
            provider_status,
            progress_callback=lambda step, status, payload=None: job.publish(
                {
                    "step": step,
                    "status": status,
                    **({"result": payload} if payload is not None else {}),
                }
            ),
        )
        explanations = {
            "en": build_explanation(verdict, "en", "simple"),
            "te": build_explanation(verdict, "te", "simple"),
            "hi": build_explanation(verdict, "hi", "simple"),
        }
        explanations[lang] = explanation
        integrity_record = {}
        try:
            if video_path.exists():
                integrity_record = generate_forensic_integrity_record(
                    video_path.read_bytes(),
                    filename=video_path.name,
                    mime_type="video/mp4",
                )
        except Exception as integ_exc:
            logger.warning("Could not compute video integrity (%s).", integ_exc)

        result = {
            "token": job_id,
            "verdict": verdict,
            "evidence_strength": video_result["evidence_strength"],
            "agreement": video_result["agreement"],
            "tool_summaries": {
                "video": video_result,
                "integrity": integrity_record,
                "nemotron": nemotron_summary,
            },
            "integrity": integrity_record,
            "nemotron": nemotron_summary,
            "trace": [
                event
                for event in job.events
                if event.get("step") not in {"investigation"}
            ],
            "limitations": video_result["limitations"],
            "explanation": explanations,
            "mode": "video fixed pipeline",
            "llm_provider_info": {
                "status": (provider_status or {}).get("status", "not configured"),
                "llm_calls": investigator_status["llm_calls"],
                "video_investigator": investigator_status["status"],
                "tool_selection": "not implemented; fixed video checks were used",
            },
        }
        job.publish({"step": "save_result", "status": "running"})
        save_result(result)
        job.publish({"step": "save_result", "status": "completed"})
    except VideoAnalysisError as exc:
        logger.info("Video analysis rejected (%s).", str(exc))
        job.publish({"step": "video_analysis", "status": "failed", "result": str(exc)})
    except Exception as exc:
        logger.error("Video analysis failed (%s).", type(exc).__name__)
        job.publish(
            {
                "step": "video_analysis",
                "status": "failed",
                "result": "Video analysis failed unexpectedly. No result was saved; try again later.",
            }
        )
    finally:
        try:
            if video_path.exists():
                video_path.unlink()
        except OSError as exc:
            logger.error("Temporary video cleanup failed (%s).", type(exc).__name__)
            job.publish(
                {
                    "step": "temporary_file_cleanup",
                    "status": "failed",
                    "result": "A temporary video file could not be removed. Contact the operator.",
                }
            )
        job.finish()


@app.get("/api/video/analyze/{job_id}/events")
async def video_analysis_events(job_id: str):
    return await analyze_events(job_id)


@app.get("/api/video/result/{token}")
async def video_result(token: str) -> dict[str, Any]:
    entry = get_result_by_token(token)
    summaries = entry.get("tool_summaries") if entry else None
    if not isinstance(summaries, dict) or not isinstance(summaries.get("video"), dict):
        raise HTTPException(status_code=404, detail="Video result not found.")
    return entry


@app.get("/api/analyze/{job_id}/events")
async def analyze_events(job_id: str):
    with ANALYSIS_JOBS_LOCK:
        job = ANALYSIS_JOBS.get(job_id)
    if job is None:
        result = get_result_by_token(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Result not found.")

        def completed_event_stream():
            for step in result.get("trace", []):
                payload = {
                    "step": step["step"],
                    "status": "completed",
                    "result": step["result"],
                }
                yield f"data: {json.dumps(payload)}\n\n"

        return StreamingResponse(
            completed_event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def event_stream():
        index = 0
        while True:
            with job.condition:
                job.condition.wait_for(
                    lambda: len(job.events) > index or job.completed,
                    timeout=10,
                )
                events = job.events[index:]
                index += len(events)
                completed = job.completed
            for event in events:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if completed:
                return
            if not events:
                yield ": keep-alive\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _process_analysis_job(
    job_id: str,
    job: AnalysisJob,
    contents: bytes,
    image_format: str,
    lang: str,
    provider_status: dict[str, Any] | None,
) -> None:
    suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[image_format]
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="veriframe_", suffix=suffix, delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(contents)

        job.publish({"step": "investigation", "status": "running"})
        result = analyze_image(
            str(temp_path),
            lang=lang,
            provider_status=provider_status,
            progress_callback=lambda step, status, payload=None: job.publish(
                {"step": step, "status": status, **({"result": payload} if payload is not None else {})}
            ),
        )
        integrity_record = generate_forensic_integrity_record(
            contents,
            filename=f"image{suffix}",
            mime_type=f"image/{image_format.lower()}",
        )
        result["integrity"] = integrity_record
        if "tool_summaries" not in result or not isinstance(result["tool_summaries"], dict):
            result["tool_summaries"] = {}
        result["tool_summaries"]["integrity"] = integrity_record
        result["token"] = job_id
        save_result(result)
        job.publish({"step": "save_result", "status": "completed"})
    except Exception as exc:
        logger.error("Image analysis job failed (%s).", type(exc).__name__)
        job.publish(
            {
                "step": "investigation",
                "status": "failed",
                "result": "Analysis failed. No result was saved; try again later.",
            }
        )
    finally:
        try:
            if temp_path and temp_path.exists():
                temp_path.unlink()
        except OSError as exc:
            logger.error("Temporary image cleanup failed (%s).", type(exc).__name__)
            job.publish(
                {
                    "step": "temporary_file_cleanup",
                    "status": "failed",
                    "result": "The temporary image could not be removed. Contact the operator.",
                }
            )
        finally:
            job.finish()


@app.get("/api/result/{token}")
async def result(token: str) -> dict[str, Any]:
    entry = get_result_by_token(token)
    if not entry:
        raise HTTPException(status_code=404, detail="Result not found.")
    return entry


@app.post("/api/result/{token}/translate")
async def translate(token: str, lang: str = "en", style: str = "simple") -> dict[str, Any]:
    entry = get_result_by_token(token)
    if not entry:
        raise HTTPException(status_code=404, detail="Result not found.")
    if lang not in {"en", "te", "hi"}:
        raise HTTPException(status_code=400, detail="Unsupported language.")
    if style not in {"simple", "detailed"}:
        raise HTTPException(status_code=400, detail="Unsupported explanation style.")
    explanation = build_explanation(entry["verdict"], lang=lang, style=style)
    return {
        "token": token,
        "lang": lang,
        "style": style,
        "explanation": explanation,
    }


@app.post("/api/result/{token}/report")
async def report(token: str, category: str = "other", comment: str = "") -> dict[str, Any]:
    entry = get_result_by_token(token)
    if not entry:
        raise HTTPException(status_code=404, detail="Result not found.")
    if category not in {"incorrect_verdict", "incorrect_evidence", "technical_issue", "other"}:
        raise HTTPException(status_code=400, detail="Unsupported report category.")
    save_report(token, category, comment.strip()[:1000])
    return {"token": token, "status": "recorded", "category": category}


@app.get("/api/result/{token}/share-card.png")
async def share_card(token: str, request: Request) -> Response:
    entry = get_result_by_token(token)
    if not entry:
        raise HTTPException(status_code=404, detail="Result not found.")
    result_url = str(request.base_url).rstrip("/") + f"/result/{token}"
    image_bytes = create_share_card(entry, result_url)
    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="very-frame-result.png"',
        },
    )


@app.get("/api/insights")
async def insights(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not INSIGHTS_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="Aggregate insights are disabled by the server operator.")
    expected = f"Bearer {INSIGHTS_ACCESS_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="A valid insights access token is required.")
    return get_insights()


@app.get("/api/samples")
async def samples() -> dict[str, Any]:
    return {"samples": []}


@app.get("/api/result/{token}/dossier")
async def result_dossier(token: str) -> HTMLResponse:
    entry = get_result_by_token(token)
    if not entry:
        raise HTTPException(status_code=404, detail="Result not found.")
    html_content = render_single_dossier_html(entry)
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/api/result/{token}/export.json")
async def result_export(token: str) -> dict[str, Any]:
    entry = get_result_by_token(token)
    if not entry:
        raise HTTPException(status_code=404, detail="Result not found.")
    return entry


# ==============================================================================
# INVESTIGATION WORKSPACE & CASE ROUTES
# ==============================================================================


class CreateCaseRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list)
    priority: str = Field(default="normal")
    investigator: str = Field(default="Lead Forensic Specialist")


class UpdateCaseRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    tags: list[str] | None = None
    investigator: str | None = None


class AddCaseNoteRequest(BaseModel):
    author: str = Field(default="Investigator")
    content: str = Field(..., min_length=1, max_length=4000)


class AttachItemRequest(BaseModel):
    token: str = Field(..., min_length=1)
    item_type: str = Field(default="image")
    label: str = Field(default="")
    notes: str = Field(default="")
    actor: str = Field(default="Investigator")


@app.post("/api/cases")
async def api_create_case(payload: CreateCaseRequest) -> dict[str, Any]:
    return create_case(
        title=payload.title,
        description=payload.description,
        tags=payload.tags,
        priority=payload.priority,
        investigator=payload.investigator,
    )


@app.get("/api/cases")
async def api_list_cases(status: str | None = None) -> dict[str, Any]:
    cases = list_cases(status=status)
    return {"cases": cases, "count": len(cases)}


@app.get("/api/cases/{case_id}")
async def api_get_case(case_id: str) -> dict[str, Any]:
    case_record = get_case(case_id)
    if not case_record:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    items = get_case_items(case_id)
    correlation = correlate_case_evidence(items)
    return {
        "case": case_record,
        "items": items,
        "correlation": correlation,
    }


@app.patch("/api/cases/{case_id}")
async def api_update_case(case_id: str, payload: UpdateCaseRequest) -> dict[str, Any]:
    updates = {k: v for k, v in payload.dict().items() if v is not None}
    updated = update_case(case_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    return updated


@app.post("/api/cases/{case_id}/notes")
async def api_add_case_note(case_id: str, payload: AddCaseNoteRequest) -> dict[str, Any]:
    updated = add_case_note(case_id, author=payload.author, content=payload.content)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    return updated


@app.post("/api/cases/{case_id}/attach")
async def api_attach_item(case_id: str, payload: AttachItemRequest) -> dict[str, Any]:
    case_record = get_case(case_id)
    if not case_record:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    try:
        attached = attach_item_to_case(
            case_id=case_id,
            token=payload.token,
            item_type=payload.item_type,
            label=payload.label,
            notes=payload.notes,
            actor=payload.actor,
        )
        return attached
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/cases/{case_id}/items/{token}")
async def api_remove_item(case_id: str, token: str) -> dict[str, Any]:
    success = remove_item_from_case(case_id, token)
    if not success:
        raise HTTPException(status_code=404, detail=f"Item '{token}' not found in case '{case_id}'.")
    return {"status": "removed", "token": token}


@app.get("/api/cases/{case_id}/audit")
async def api_get_case_audit(case_id: str) -> dict[str, Any]:
    case_record = get_case(case_id)
    if not case_record:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    logs = get_case_audit_logs(case_id)
    return {"case_id": case_id, "logs": logs}


@app.get("/api/cases/{case_id}/report")
async def api_case_report(case_id: str) -> HTMLResponse:
    case_record = get_case(case_id)
    if not case_record:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    items = get_case_items(case_id)
    correlation = correlate_case_evidence(items)
    html_content = render_case_report_html(case_record, items, correlation)
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/api/cases/{case_id}/export.json")
async def api_case_export(case_id: str) -> dict[str, Any]:
    case_record = get_case(case_id)
    if not case_record:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    items = get_case_items(case_id)
    correlation = correlate_case_evidence(items)
    audit = get_case_audit_logs(case_id)
    return {
        "case": case_record,
        "items": items,
        "correlation": correlation,
        "audit_logs": audit,
    }


# ==============================================================================
# NVIDIA NEMOTRON VIDEO UNDERSTANDING & GROUNDED Q&A ROUTES
# ==============================================================================


@app.get("/api/nvidia/status")
async def nvidia_status() -> dict[str, Any]:
    return get_nvidia_status()


class AskVideoRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    token: str | None = None


@app.post("/api/video/{token}/ask")
async def api_ask_video(token: str, payload: AskVideoRequest) -> dict[str, Any]:
    entry = get_result_by_token(token)
    if not entry:
        raise HTTPException(status_code=404, detail="Video analysis result not found.")

    summaries = entry.get("tool_summaries") or {}
    nemotron_data = summaries.get("nemotron") or entry.get("nemotron") or {}
    video_summary = summaries.get("video") or {}
    video_info = video_summary.get("video_info") or {}

    response = ask_video_nemotron(payload.question, nemotron_data, video_info)
    response["token"] = token
    return response


@app.post("/api/video/ask")
async def api_ask_video_alt(payload: AskVideoRequest) -> dict[str, Any]:
    if not payload.token:
        raise HTTPException(status_code=400, detail="Video analysis token is required.")
    return await api_ask_video(payload.token, payload)


@app.get("/")
async def index() -> dict[str, str]:
    return {"status": "ok"}
