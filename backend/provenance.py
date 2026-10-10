from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from PIL import Image, UnidentifiedImageError


def read_metadata(image_path: str) -> dict[str, Any]:
    try:
        with Image.open(image_path) as image:
            exif = image.getexif()
            info_keys = sorted(str(key) for key in image.info)
    except (OSError, UnidentifiedImageError):
        return {"exif": "not verifiable", "metadata_keys": []}
    return {
        "exif": "present" if exif else "missing",
        "metadata_keys": info_keys,
        "note": "Missing metadata is not evidence either way.",
    }


def check_c2pa(image_path: str) -> dict[str, Any]:
    c2pa_tool = shutil.which("c2patool")
    if not c2pa_tool:
        return {
            "status": "not verifiable",
            "message": "c2patool is not installed; no C2PA verification was performed.",
        }
    try:
        completed = subprocess.run(
            [c2pa_tool, "-i", image_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {
            "status": "not verifiable",
            "message": "c2patool could not verify C2PA data for this image.",
        }

    if completed.returncode != 0:
        return {
            "status": "not verifiable",
            "message": "c2patool returned an error; C2PA status is not verifiable.",
        }
    try:
        payload = json.loads(completed.stdout)
    except (ValueError, TypeError):
        return {
            "status": "not verifiable",
            "message": "c2patool returned an unrecognized response; C2PA status is not verifiable.",
        }

    has_manifest = bool(payload.get("active_manifest")) or bool(payload.get("manifests"))
    return {
        "status": "present" if has_manifest else "missing",
        "message": (
            "A C2PA manifest was found; this is not by itself proof of authenticity."
            if has_manifest
            else "No C2PA manifest was reported. Missing provenance is not evidence either way."
        ),
    }


def read_provenance(image_path: str) -> dict[str, Any]:
    return {
        "exif": read_metadata(image_path),
        "c2pa": check_c2pa(image_path),
        "summary": "Missing metadata is not evidence of AI generation or authenticity.",
    }
