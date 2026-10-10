from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageFilter, ImageStat

from . import detectors
from .config import (
    CAP_DISAGREEMENT_DELTA,
    FRAME_SAMPLE_INTERVAL_SECONDS,
    LIKELY_AI_THRESHOLD,
    MAX_ANALYZED_FRAMES,
    MAX_FACE_TRACKS,
    NO_SIGNS_THRESHOLD,
    VIDEO_ANALYSIS_TIMEOUT_SECONDS,
    VIDEO_MAX_DURATION_SECONDS,
    VIDEO_MAX_FPS,
    VIDEO_MAX_RESOLUTION_HEIGHT,
    VIDEO_MAX_RESOLUTION_WIDTH,
    VIDEO_MAX_SIZE_BYTES,
    VIDEO_SCENE_SAMPLE_INTERVAL_SECONDS,
    VIDEO_SCENE_THRESHOLD,
)

ProgressCallback = Callable[[str, str, Any | None], None]

_SUPPORTED_CONTAINERS = {
    ".mp4": ("video/mp4", {b"ftyp"}),
    ".mov": ("video/quicktime", {b"ftyp"}),
    ".webm": ("video/webm", {b"\x1aE\xdf\xa3"}),
}


class VideoAnalysisError(ValueError):
    """A user-correctable video validation or analysis error."""


def _emit(
    callback: ProgressCallback | None,
    step: str,
    status: str,
    result: Any | None = None,
) -> None:
    if callback:
        callback(step, status, result)


def validate_video_header(filename: str, mime_type: str | None, header: bytes) -> dict[str, str]:
    extension = Path(filename).suffix.lower()
    expected = _SUPPORTED_CONTAINERS.get(extension)
    if expected is None:
        raise VideoAnalysisError("Unsupported video extension. Allowed formats: MP4, MOV, and WebM.")

    expected_mime, signatures = expected
    normalized_mime = mime_type.split(";", 1)[0].strip().lower() if mime_type else ""
    if normalized_mime and normalized_mime != expected_mime:
        raise VideoAnalysisError("The video extension and MIME type do not match.")

    if extension == ".webm":
        signature_matches = header.startswith(next(iter(signatures)))
    else:
        signature_matches = len(header) >= 12 and header[4:8] in signatures
    if not signature_matches:
        raise VideoAnalysisError("The file signature does not match a supported MP4, MOV, or WebM container.")

    return {
        "extension": extension,
        "mime_type": expected_mime,
    }


def _remaining_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise VideoAnalysisError("Video analysis exceeded the configured processing time limit.")
    return remaining


def _require_ffmpeg() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg:
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    if not ffprobe and ffmpeg:
        candidate = Path(ffmpeg).parent / ("ffprobe.exe" if sys.platform == "win32" else "ffprobe")
        if candidate.exists():
            ffprobe = str(candidate)
        else:
            ffprobe = ffmpeg
    if not ffmpeg:
        raise VideoAnalysisError(
            "Video analysis requires FFmpeg on the backend PATH or installed in the environment."
        )
    return ffmpeg, ffprobe or ffmpeg


def _probe_video_with_ffmpeg(ffmpeg: str, path: str | Path) -> dict[str, Any]:
    completed = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostdin", "-i", str(path)],
        capture_output=True,
        text=True,
        timeout=30.0,
        check=False,
    )
    stderr = completed.stderr
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    if not dur_match:
        raise VideoAnalysisError("The video duration could not be determined.")
    duration = float(dur_match.group(1)) * 3600 + float(dur_match.group(2)) * 60 + float(dur_match.group(3))
    if duration <= 0 or duration > VIDEO_MAX_DURATION_SECONDS:
        raise VideoAnalysisError(
            f"Video exceeds the {VIDEO_MAX_DURATION_SECONDS}-second duration limit."
        )

    vid_match = re.search(r"Stream.*Video:\s*(\w+).*?,\s*(\d+)x(\d+)", stderr)
    if not vid_match:
        raise VideoAnalysisError("The file does not contain a readable video track.")
    codec = vid_match.group(1)
    width, height = int(vid_match.group(2)), int(vid_match.group(3))
    dimensions_fit = (
        width <= VIDEO_MAX_RESOLUTION_WIDTH and height <= VIDEO_MAX_RESOLUTION_HEIGHT
    ) or (
        width <= VIDEO_MAX_RESOLUTION_HEIGHT and height <= VIDEO_MAX_RESOLUTION_WIDTH
    )
    if not dimensions_fit:
        raise VideoAnalysisError(
            f"Video resolution exceeds the configured {VIDEO_MAX_RESOLUTION_WIDTH}x{VIDEO_MAX_RESOLUTION_HEIGHT} limit."
        )

    fps_match = re.search(r"([0-9.]+)\s*fps", stderr) or re.search(r"([0-9.]+)\s*tbr", stderr)
    frame_rate = float(fps_match.group(1)) if fps_match else 24.0
    if frame_rate > VIDEO_MAX_FPS:
        raise VideoAnalysisError(f"Video exceeds the {VIDEO_MAX_FPS:g} FPS limit.")

    audio_streams = re.findall(r"Stream.*Audio:\s*(\w+)", stderr)
    bitrate_match = re.search(r"bitrate:\s*(\d+)\s*kb/s", stderr)
    bitrate = int(bitrate_match.group(1)) * 1000 if bitrate_match else None

    return {
        "duration_seconds": round(duration, 3),
        "width": width,
        "height": height,
        "fps": round(frame_rate, 3),
        "video_codec": codec,
        "bitrate_bps": bitrate,
        "frame_count": int(duration * frame_rate),
        "container": Path(path).suffix.lstrip(".").lower() or "mp4",
        "has_audio": bool(audio_streams),
        "audio_codec": audio_streams[0] if audio_streams else None,
        "audio_authenticity_assessed": False,
    }


def _parse_rate(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        numerator, denominator = value.split("/", 1)
        denominator_value = float(denominator)
        rate = float(numerator) / denominator_value if denominator_value else math.nan
    except (ValueError, ZeroDivisionError):
        return None
    return rate if math.isfinite(rate) and rate > 0 else None


def probe_video(path: str | Path, deadline: float | None = None) -> dict[str, Any]:
    ffmpeg, ffprobe = _require_ffmpeg()
    started = time.monotonic()
    effective_deadline = deadline or (started + VIDEO_ANALYSIS_TIMEOUT_SECONDS)
    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=min(30.0, _remaining_timeout(effective_deadline)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoAnalysisError("Video metadata inspection timed out. Try a shorter video.") from exc
    except OSError as exc:
        try:
            return _probe_video_with_ffmpeg(ffmpeg, path)
        except Exception:
            raise VideoAnalysisError("ffprobe could not inspect this video file.") from exc

    if completed.returncode != 0:
        try:
            return _probe_video_with_ffmpeg(ffmpeg, path)
        except Exception:
            raise VideoAnalysisError(
                "The video container is corrupted or could not be read by ffprobe."
            )

    try:
        payload = json.loads(completed.stdout)
    except (ValueError, TypeError) as exc:
        raise VideoAnalysisError("ffprobe returned invalid video metadata.") from exc

    format_info = payload.get("format")
    streams = payload.get("streams")
    if not isinstance(format_info, dict) or not isinstance(streams, list):
        raise VideoAnalysisError("The file does not contain a readable video stream.")
    video_streams = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"]
    if not video_streams:
        raise VideoAnalysisError("The file does not contain a video track.")
    video_stream = video_streams[0]

    duration_value = format_info.get("duration") or video_stream.get("duration")
    try:
        duration = float(duration_value)
    except (TypeError, ValueError) as exc:
        raise VideoAnalysisError("The video duration could not be determined.") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise VideoAnalysisError("The video duration is invalid.")
    if duration > VIDEO_MAX_DURATION_SECONDS:
        raise VideoAnalysisError(
            f"Video exceeds the {VIDEO_MAX_DURATION_SECONDS}-second duration limit."
        )

    try:
        width = int(video_stream["width"])
        height = int(video_stream["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise VideoAnalysisError("The video resolution could not be determined.") from exc
    if width <= 0 or height <= 0:
        raise VideoAnalysisError("The video resolution is invalid.")
    dimensions_fit = (
        width <= VIDEO_MAX_RESOLUTION_WIDTH and height <= VIDEO_MAX_RESOLUTION_HEIGHT
    ) or (
        width <= VIDEO_MAX_RESOLUTION_HEIGHT and height <= VIDEO_MAX_RESOLUTION_WIDTH
    )
    if not dimensions_fit:
        raise VideoAnalysisError(
            f"Video resolution exceeds the configured {VIDEO_MAX_RESOLUTION_WIDTH}x{VIDEO_MAX_RESOLUTION_HEIGHT} limit."
        )

    frame_rate = _parse_rate(video_stream.get("avg_frame_rate")) or _parse_rate(
        video_stream.get("r_frame_rate")
    )
    if frame_rate is None:
        raise VideoAnalysisError("The video frame rate could not be determined.")
    if frame_rate > VIDEO_MAX_FPS:
        raise VideoAnalysisError(f"Video exceeds the {VIDEO_MAX_FPS:g} FPS limit.")

    format_names = str(format_info.get("format_name", "")).lower()
    extension = Path(path).suffix.lower()
    if extension in {".mp4", ".mov"} and not any(
        name in format_names for name in ("mov", "mp4", "3gp", "mj2")
    ):
        raise VideoAnalysisError("The detected container does not match the MP4/MOV file extension.")
    if extension == ".webm" and "webm" not in format_names and "matroska" not in format_names:
        raise VideoAnalysisError("The detected container does not match the WebM file extension.")

    audio_streams = [
        stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "audio"
    ]
    bitrate_value = video_stream.get("bit_rate") or format_info.get("bit_rate")
    try:
        bitrate = int(bitrate_value) if bitrate_value else None
    except (TypeError, ValueError):
        bitrate = None
    frame_count_value = video_stream.get("nb_frames")
    try:
        frame_count = int(frame_count_value) if frame_count_value not in (None, "N/A") else None
    except (TypeError, ValueError):
        frame_count = None

    return {
        "duration_seconds": round(duration, 3),
        "width": width,
        "height": height,
        "fps": round(frame_rate, 3),
        "video_codec": str(video_stream.get("codec_name") or "unknown"),
        "bitrate_bps": bitrate,
        "frame_count": frame_count,
        "container": format_names or "unknown",
        "has_audio": bool(audio_streams),
        "audio_codec": str(audio_streams[0].get("codec_name") or "unknown") if audio_streams else None,
        "audio_authenticity_assessed": False,
    }


def detect_scene_changes(
    path: str | Path,
    duration: float,
    deadline: float,
) -> list[float] | None:
    ffmpeg, _ffprobe = _require_ffmpeg()
    filter_expression = (
        f"fps=1/{VIDEO_SCENE_SAMPLE_INTERVAL_SECONDS:g},"
        "scale=320:-2:flags=fast_bilinear,"
        f"select='gt(scene,{VIDEO_SCENE_THRESHOLD:g})',showinfo"
    )
    try:
        completed = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-nostdin",
                "-v",
                "info",
                "-i",
                str(path),
                "-vf",
                filter_expression,
                "-an",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=_remaining_timeout(deadline),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    except OSError:
        return None
    if completed.returncode != 0:
        return None

    timestamps = []
    for match in re.finditer(r"pts_time:([0-9]+(?:\.[0-9]+)?)", completed.stderr):
        timestamp = float(match.group(1))
        if 0 < timestamp < duration:
            timestamps.append(timestamp)
    return timestamps


def choose_sample_timestamps(
    duration: float,
    scene_changes: list[float],
    max_frames: int = MAX_ANALYZED_FRAMES,
) -> list[float]:
    if duration <= 0 or max_frames <= 0:
        return []
    limit = max(1, max_frames)
    desired_uniform = max(1, math.ceil(duration / FRAME_SAMPLE_INTERVAL_SECONDS))
    uniform_count = min(limit, desired_uniform, max(1, limit // 2))
    uniform = [
        (index + 0.5) * duration / uniform_count
        for index in range(uniform_count)
    ]
    scene_budget = max(0, limit - len(uniform))
    ordered_scenes = sorted({round(value, 3) for value in scene_changes if 0 < value < duration})
    if scene_budget and ordered_scenes:
        if len(ordered_scenes) > scene_budget:
            positions = [
                round(index * (len(ordered_scenes) - 1) / max(1, scene_budget - 1))
                for index in range(scene_budget)
            ]
            ordered_scenes = [ordered_scenes[index] for index in positions]
        else:
            ordered_scenes = ordered_scenes[:scene_budget]

    tolerance = min(0.5, duration / max(1, limit) * 0.1)
    selected = list(uniform)
    for timestamp in ordered_scenes:
        if len(selected) >= limit:
            break
        if all(abs(timestamp - existing) > tolerance for existing in selected):
            selected.append(timestamp)
    if len(selected) < limit:
        for index in range(limit):
            timestamp = (index + 0.5) * duration / limit
            if all(abs(timestamp - existing) > tolerance for existing in selected):
                selected.append(timestamp)
            if len(selected) >= limit:
                break
    return sorted(selected[:limit])


def _extract_frame(
    video_path: str | Path,
    timestamp: float,
    output_path: Path,
    deadline: float,
) -> None:
    ffmpeg, _ffprobe = _require_ffmpeg()
    try:
        completed = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-nostdin",
                "-v",
                "error",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-an",
                "-y",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=_remaining_timeout(deadline),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoAnalysisError("Frame extraction exceeded the video processing time limit.") from exc
    except OSError as exc:
        raise VideoAnalysisError("FFmpeg could not decode the selected video frame.") from exc
    if completed.returncode != 0 or not output_path.is_file():
        stderr = completed.stderr.lower()
        if "unknown decoder" in stderr or "decoder not found" in stderr or "unsupported codec" in stderr:
            raise VideoAnalysisError(
                "This video uses a codec that the installed FFmpeg cannot currently decode."
            )
        raise VideoAnalysisError("The video is corrupted or FFmpeg could not decode a sampled frame.")


def assess_frame_quality(frame_path: str | Path) -> dict[str, Any]:
    try:
        with Image.open(frame_path) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            grayscale = rgb.convert("L")
            brightness = ImageStat.Stat(grayscale).mean[0]
            edges = grayscale.filter(ImageFilter.FIND_EDGES)
            edge_detail = ImageStat.Stat(edges).stddev[0]
            edges.close()
            grayscale.close()
            rgb.close()
    except (OSError, ValueError) as exc:
        raise VideoAnalysisError("FFmpeg produced a frame that could not be decoded as an image.") from exc

    reasons = []
    if min(width, height) < 160:
        reasons.append("low_resolution")
    if brightness < 4:
        reasons.append("very_dark")
    if brightness > 251:
        reasons.append("overexposed")
    if edge_detail < 1.0:
        reasons.append("low_detail")
    return {
        "width": width,
        "height": height,
        "brightness_mean": round(brightness, 2),
        "edge_detail": round(edge_detail, 2),
        "usable": not reasons,
        "limitations": reasons,
    }


def _frame_signal(ensemble: dict[str, Any]) -> dict[str, Any]:
    detectors_for_frame = ensemble.get("detectors", [])
    scores = [
        float(item["score"])
        for item in detectors_for_frame
        if item.get("status") == "ok" and isinstance(item.get("score"), (int, float))
    ]
    enough_detectors = len(scores) >= 2
    mean_score = sum(scores) / len(scores) if enough_detectors else None
    spread = max(scores) - min(scores) if enough_detectors else None
    agreed = spread is not None and spread <= CAP_DISAGREEMENT_DELTA
    if not enough_detectors:
        signal = "insufficient_detectors"
    elif not agreed:
        signal = "detector_disagreement"
    elif mean_score is not None and mean_score >= LIKELY_AI_THRESHOLD:
        signal = "suspicious"
    elif mean_score is not None and mean_score <= NO_SIGNS_THRESHOLD:
        signal = "no_ai_signs"
    else:
        signal = "ambiguous"
    return {
        "detectors": detectors_for_frame,
        "mean_score": round(mean_score, 2) if mean_score is not None else None,
        "agreement": "high" if agreed else ("low" if enough_detectors else "unavailable"),
        "score_spread": round(spread, 2) if spread is not None else None,
        "signal": signal,
        "status": ensemble.get("status", "unavailable"),
    }


def aggregate_video_evidence(
    frames: list[dict[str, Any]],
    scene_count: int,
    video_info: dict[str, Any],
) -> dict[str, Any]:
    scored_frames = [
        frame
        for frame in frames
        if frame.get("quality", {}).get("usable") and frame.get("mean_score") is not None
    ]
    suspicious = [frame for frame in scored_frames if frame.get("signal") == "suspicious"]
    normal = [frame for frame in scored_frames if frame.get("signal") == "no_ai_signs"]
    disagreements = [frame for frame in frames if frame.get("signal") == "detector_disagreement"]
    scene_coverage = len({frame.get("scene_id") for frame in scored_frames})
    unstable_pairs = []
    for previous, current in zip(scored_frames, scored_frames[1:]):
        delta = abs(float(previous["mean_score"]) - float(current["mean_score"]))
        if delta > CAP_DISAGREEMENT_DELTA:
            unstable_pairs.append(
                {
                    "start_timestamp": previous["timestamp"],
                    "end_timestamp": current["timestamp"],
                    "score_delta": round(delta, 2),
                }
            )

    enough_frames = len(scored_frames) >= 4
    adequate_scene_coverage = scene_coverage >= min(2, max(1, scene_count))
    disagreement_share = len(disagreements) / max(1, len(frames))
    suspicious_scene_coverage = len({frame.get("scene_id") for frame in suspicious})
    distributed_suspicion = (
        len(suspicious) >= max(2, math.ceil(len(scored_frames) * 0.5))
        and suspicious_scene_coverage >= min(2, max(1, scene_count))
    )
    stable_detector_scores = not unstable_pairs and disagreement_share <= 0.25

    if (
        enough_frames
        and adequate_scene_coverage
        and distributed_suspicion
        and stable_detector_scores
    ):
        verdict = "Likely AI"
        evidence_strength = "Moderate"
    elif (
        enough_frames
        and adequate_scene_coverage
        and len(normal) == len(scored_frames)
        and not suspicious
        and stable_detector_scores
    ):
        verdict = "No AI signs found"
        evidence_strength = "Moderate"
    else:
        verdict = "Inconclusive"
        evidence_strength = "Weak" if not enough_frames or not scored_frames else "Moderate"

    agreement = "High" if enough_frames and not disagreements else "Low"
    if disagreements or unstable_pairs:
        agreement = "Low"

    return {
        "verdict": verdict,
        "evidence_strength": evidence_strength,
        "agreement": agreement,
        "analyzed_frame_count": len(frames),
        "scored_frame_count": len(scored_frames),
        "suspicious_signal_count": len(suspicious),
        "detector_disagreement_count": len(disagreements),
        "scene_coverage_count": scene_coverage,
        "scene_count": scene_count,
        "suspicious_frame_timestamps": [frame["timestamp"] for frame in suspicious],
        "temporal_checks": {
            "status": "ok" if len(scored_frames) >= 2 else "insufficient_evidence",
            "unstable_neighbor_pairs": unstable_pairs,
            "note": "Only adjacent sampled-frame detector-score changes were checked; face identity and motion were not assessed.",
        },
        "audio_authenticity_assessed": False,
        "face_tracking": {
            "status": "unavailable",
            "max_face_tracks_configured": MAX_FACE_TRACKS,
            "tracks": [],
            "message": "No face detector/tracker is configured; face-based checks were not available for this video.",
        },
        "what_was_not_checked": [
            "Face-based identity or region tracking (no face tracker is configured).",
            "Audio authenticity and audio/video synchronization.",
            "Motion consistency beyond adjacent sampled-frame detector-score changes.",
            "Causal attribution of any signal to AI generation or manipulation.",
        ],
        "limitations": [
            "This result is an estimate, not proof of authenticity or AI generation.",
            "Detector scores and decision thresholds are not calibrated probabilities.",
            "The verdict requires evidence across sampled frames and scenes; sparse signals remain inconclusive.",
            "Audio presence and codec metadata do not establish audio authenticity.",
        ],
        "video_info": video_info,
    }


def analyze_video(
    video_path: str | Path,
    progress_callback: ProgressCallback | None = None,
    return_sampled_images: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + VIDEO_ANALYSIS_TIMEOUT_SECONDS
    _emit(progress_callback, "get_video_info", "running")
    video_info = probe_video(video_path, deadline)
    _emit(progress_callback, "get_video_info", "completed", video_info)

    _emit(progress_callback, "detect_scenes", "running")
    detected_scene_changes = detect_scene_changes(video_path, video_info["duration_seconds"], deadline)
    scene_status = "ok" if detected_scene_changes is not None else "unavailable"
    scene_changes = detected_scene_changes or []
    _emit(
        progress_callback,
        "detect_scenes",
        "completed" if scene_changes else "unavailable",
        {"scene_change_count": len(scene_changes), "status": scene_status},
    )

    timestamps = choose_sample_timestamps(video_info["duration_seconds"], scene_changes)
    if not timestamps:
        raise VideoAnalysisError("No representative video frames could be selected.")
    frames: list[dict[str, Any]] = []
    sampled_images: list[dict[str, Any]] = []
    scene_points = [0.0, *scene_changes]
    _emit(progress_callback, "sample_frames", "running")
    with tempfile.TemporaryDirectory(prefix="veriframe_video_frames_") as frame_directory:
        for index, timestamp in enumerate(timestamps):
            _remaining_timeout(deadline)
            frame_path = Path(frame_directory) / f"frame_{index:04d}.jpg"
            _extract_frame(video_path, timestamp, frame_path, deadline)
            if return_sampled_images and len(sampled_images) < 6:
                sampled_images.append({
                    "timestamp": round(timestamp, 3),
                    "frame_index": round(timestamp * video_info["fps"]),
                    "frame_bytes": frame_path.read_bytes(),
                })
            quality = assess_frame_quality(frame_path)
            nearest_scene = max(
                (point for point in scene_points if point <= timestamp),
                default=0.0,
            )
            scene_id = scene_points.index(nearest_scene) + 1
            frame: dict[str, Any] = {
                "timestamp": round(timestamp, 3),
                "frame_index": round(timestamp * video_info["fps"]),
                "scene_id": scene_id,
                "quality": quality,
                "status": "quality_rejected" if not quality["usable"] else "pending",
            }
            _emit(
                progress_callback,
                "assess_frame_quality",
                "completed",
                {"timestamp": frame["timestamp"], **quality},
            )
            if quality["usable"]:
                _remaining_timeout(deadline)
                _emit(
                    progress_callback,
                    "run_frame_detectors",
                    "running",
                    {"timestamp": frame["timestamp"]},
                )
                frame.update(_frame_signal(detectors.run_detector_ensemble(frame_path)))
                _remaining_timeout(deadline)
                frame["status"] = "completed" if frame["mean_score"] is not None else "insufficient_detectors"
                _emit(
                    progress_callback,
                    "run_frame_detectors",
                    "completed" if frame["mean_score"] is not None else "unavailable",
                    {
                        "timestamp": frame["timestamp"],
                        "signal": frame["signal"],
                        "agreement": frame["agreement"],
                    },
                )
            else:
                frame.update(
                    {
                        "detectors": [],
                        "mean_score": None,
                        "agreement": "unavailable",
                        "score_spread": None,
                        "signal": "quality_limited",
                    }
                )
            frames.append(frame)
    _emit(
        progress_callback,
        "sample_frames",
        "completed",
        {"selected_frame_count": len(frames), "frame_budget": MAX_ANALYZED_FRAMES},
    )

    _emit(progress_callback, "run_temporal_checks", "running")
    scene_count = max(1, len(scene_changes) + 1)
    aggregate = aggregate_video_evidence(frames, scene_count, video_info)
    _emit(
        progress_callback,
        "run_temporal_checks",
        "completed",
        aggregate["temporal_checks"],
    )
    _emit(progress_callback, "aggregate_evidence", "completed", {
        "verdict": aggregate["verdict"],
        "evidence_strength": aggregate["evidence_strength"],
        "analyzed_frame_count": aggregate["analyzed_frame_count"],
        "suspicious_signal_count": aggregate["suspicious_signal_count"],
    })

    aggregate.update(
        {
            "frames": frames,
            "scene_changes": [round(value, 3) for value in scene_changes],
            "scene_detection_status": scene_status,
            "sampling": {
                "method": "uniform sampling across duration plus FFmpeg scene-change sampling",
                "frame_budget": MAX_ANALYZED_FRAMES,
                "interval_seconds": FRAME_SAMPLE_INTERVAL_SECONDS,
            },
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
    )
    if return_sampled_images:
        aggregate["_sampled_images"] = sampled_images
    return aggregate
