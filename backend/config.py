from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(10 * 1024 * 1024)))
MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", "10000000"))
ALLOWED_TYPES = {"PNG", "JPEG", "WEBP"}

VIDEO_MAX_SIZE_MB = int(os.getenv("VIDEO_MAX_SIZE_MB", "100"))
VIDEO_MAX_SIZE_BYTES = VIDEO_MAX_SIZE_MB * 1024 * 1024
VIDEO_MAX_DURATION_SECONDS = int(os.getenv("VIDEO_MAX_DURATION_SECONDS", "600"))
VIDEO_MAX_RESOLUTION_WIDTH = int(os.getenv("VIDEO_MAX_RESOLUTION_WIDTH", "1920"))
VIDEO_MAX_RESOLUTION_HEIGHT = int(os.getenv("VIDEO_MAX_RESOLUTION_HEIGHT", "1080"))
VIDEO_MAX_FPS = float(os.getenv("VIDEO_MAX_FPS", "60"))
MAX_ANALYZED_FRAMES = int(os.getenv("MAX_ANALYZED_FRAMES", "24"))
FRAME_SAMPLE_INTERVAL_SECONDS = float(os.getenv("FRAME_SAMPLE_INTERVAL_SECONDS", "5"))
VIDEO_SCENE_SAMPLE_INTERVAL_SECONDS = float(os.getenv("VIDEO_SCENE_SAMPLE_INTERVAL_SECONDS", "2"))
VIDEO_SCENE_THRESHOLD = float(os.getenv("VIDEO_SCENE_THRESHOLD", "0.30"))
MAX_FACE_TRACKS = int(os.getenv("MAX_FACE_TRACKS", "0"))
VIDEO_ANALYSIS_TIMEOUT_SECONDS = int(os.getenv("VIDEO_ANALYSIS_TIMEOUT_SECONDS", "300"))
if min(
    VIDEO_MAX_SIZE_MB,
    VIDEO_MAX_DURATION_SECONDS,
    VIDEO_MAX_RESOLUTION_WIDTH,
    VIDEO_MAX_RESOLUTION_HEIGHT,
    VIDEO_MAX_FPS,
    MAX_ANALYZED_FRAMES,
    FRAME_SAMPLE_INTERVAL_SECONDS,
    VIDEO_SCENE_SAMPLE_INTERVAL_SECONDS,
    VIDEO_ANALYSIS_TIMEOUT_SECONDS,
) <= 0:
    raise ValueError("Video processing limits and sampling settings must be positive.")
if not 0 < VIDEO_SCENE_THRESHOLD <= 1:
    raise ValueError("VIDEO_SCENE_THRESHOLD must be greater than 0 and no greater than 1.")

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
VISION_MODEL = os.getenv("VISION_MODEL")
INSIGHTS_ACCESS_TOKEN = os.getenv("INSIGHTS_ACCESS_TOKEN")

# NVIDIA Nemotron Multimodal Video Reasoning Configuration
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "").strip()
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1/chat/completions").strip()
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning").strip()
NVIDIA_MAX_TOKENS = int(os.getenv("NVIDIA_MAX_TOKENS", "2048"))
NVIDIA_REASONING_BUDGET = int(os.getenv("NVIDIA_REASONING_BUDGET", "1024"))

DETECTOR_A_MODEL = os.getenv("DETECTOR_A_MODEL", "").strip()
DETECTOR_A_AI_LABEL = os.getenv("DETECTOR_A_AI_LABEL", "").strip()
DETECTOR_B_MODEL = os.getenv("DETECTOR_B_MODEL", "").strip()
DETECTOR_B_AI_LABEL = os.getenv("DETECTOR_B_AI_LABEL", "").strip()
DETECTOR_C_MODEL = os.getenv("DETECTOR_C_MODEL", "").strip()
DETECTOR_C_AI_LABEL = os.getenv("DETECTOR_C_AI_LABEL", "").strip()
DEMO_DETECTORS = os.getenv("DEMO_DETECTORS", "false").lower() in ("true", "1", "yes")

# TODO: Tune thresholds only from a verified, labeled benchmark.
LIKELY_AI_THRESHOLD = 80
NO_SIGNS_THRESHOLD = 25
CAP_DISAGREEMENT_DELTA = 30
MIN_CONFIGURED_DETECTORS = 2
MIN_IMAGE_SIDE_PIXELS = 250
MIN_IMAGE_PIXEL_COUNT = 250_000

INCONCLUSIVE_MESSAGE = "The evidence is mixed or weak. More reliable source material may change the result."
