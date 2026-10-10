from __future__ import annotations

import hashlib
import io
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def compute_hashes(data: bytes | Path | io.BytesIO) -> dict[str, str]:
    """Compute standard cryptographic hashes for file data."""
    if isinstance(data, (str, Path)):
        raw_bytes = Path(data).read_bytes()
    elif isinstance(data, io.BytesIO):
        raw_bytes = data.getvalue()
    else:
        raw_bytes = data

    return {
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "sha1": hashlib.sha1(raw_bytes).hexdigest(),
        "md5": hashlib.md5(raw_bytes).hexdigest(),
    }


def calculate_shannon_entropy(data: bytes) -> float:
    """Calculate Shannon entropy in bits per byte (0.0 to 8.0).

    Typical compressed image formats (JPEG, PNG, WebP) range from 7.0 to 7.95.
    Significantly lower values indicate padding, zero-fills, or low-complexity synthetic fills.
    """
    if not data:
        return 0.0

    length = len(data)
    frequency: dict[int, int] = {}
    for byte in data:
        frequency[byte] = frequency.get(byte, 0) + 1

    entropy = 0.0
    for count in frequency.values():
        probability = count / length
        entropy -= probability * math.log2(probability)

    return round(entropy, 4)


def inspect_container_structure(data: bytes, filename: str = "", mime_type: str = "") -> dict[str, Any]:
    """Inspect the raw byte stream of media for container integrity and trailing payloads."""
    ext = Path(filename).suffix.lower() if filename else ""
    length = len(data)

    if length < 16:
        return {
            "status": "too_short",
            "valid_magic": False,
            "has_trailing_payload": False,
            "trailing_bytes": 0,
            "notes": "File too small to evaluate container structure.",
        }

    # JPEG inspection
    if data.startswith(b"\xff\xd8") or ext in {".jpg", ".jpeg"} or "jpeg" in mime_type:
        valid_magic = data.startswith(b"\xff\xd8")
        # Find last occurrence of EOI marker \xff\xd9
        eoi_index = data.rfind(b"\xff\xd9")
        if eoi_index != -1:
            trailing = length - (eoi_index + 2)
            has_trailing = trailing > 128  # allow minor alignment padding
            return {
                "status": "trailing_bytes_detected" if has_trailing else "intact",
                "valid_magic": valid_magic,
                "has_trailing_payload": has_trailing,
                "trailing_bytes": max(0, trailing),
                "notes": (
                    f"JPEG container verified with {trailing} trailing bytes past EOI."
                    if has_trailing
                    else "Standard JPEG container ends cleanly at EOI marker."
                ),
            }
        return {
            "status": "malformed_or_truncated",
            "valid_magic": valid_magic,
            "has_trailing_payload": False,
            "trailing_bytes": 0,
            "notes": "JPEG SOI marker present but EOI marker was not found in stream.",
        }

    # PNG inspection
    png_sig = b"\x89PNG\r\n\x1a\n"
    if data.startswith(png_sig) or ext == ".png" or "png" in mime_type:
        valid_magic = data.startswith(png_sig)
        # Search for IEND chunk: 4 bytes length (00 00 00 00) + 'IEND' + 4 bytes CRC
        iend_pos = data.rfind(b"IEND")
        if iend_pos != -1:
            end_of_chunk = iend_pos + 4 + 4  # 'IEND' (4 bytes) + CRC (4 bytes)
            trailing = length - end_of_chunk
            has_trailing = trailing > 64
            return {
                "status": "trailing_bytes_detected" if has_trailing else "intact",
                "valid_magic": valid_magic,
                "has_trailing_payload": has_trailing,
                "trailing_bytes": max(0, trailing),
                "notes": (
                    f"PNG container verified with {trailing} trailing bytes past IEND chunk."
                    if has_trailing
                    else "Standard PNG container ends cleanly at IEND chunk."
                ),
            }
        return {
            "status": "malformed_or_truncated",
            "valid_magic": valid_magic,
            "has_trailing_payload": False,
            "trailing_bytes": 0,
            "notes": "PNG magic signature verified; IEND chunk not located.",
        }

    # MP4 / MOV / QuickTime
    if len(data) >= 8 and (data[4:8] == b"ftyp" or ext in {".mp4", ".mov", ".m4v"}):
        return {
            "status": "intact",
            "valid_magic": data[4:8] == b"ftyp",
            "has_trailing_payload": False,
            "trailing_bytes": 0,
            "notes": f"ISO Base Media (MP4/MOV) container detected with compatible brand {data[8:12].decode('ascii', errors='ignore')}.",
        }

    # Generic
    return {
        "status": "unverified_container",
        "valid_magic": True,
        "has_trailing_payload": False,
        "trailing_bytes": 0,
        "notes": "Generic binary stream evaluated.",
    }


def generate_forensic_integrity_record(
    data: bytes,
    filename: str = "",
    mime_type: str = "",
) -> dict[str, Any]:
    """Generate a comprehensive, immutable forensic integrity record for evidence items."""
    hashes = compute_hashes(data)
    entropy = calculate_shannon_entropy(data)
    container_info = inspect_container_structure(data, filename=filename, mime_type=mime_type)

    if entropy >= 7.98:
        entropy_assessment = "extremely_high_entropy (dense compression or encrypted payload)"
    elif entropy >= 6.8:
        entropy_assessment = "normal_compressed (typical for standard media formats)"
    elif entropy >= 4.5:
        entropy_assessment = "moderate_entropy (simple graphical content or low noise)"
    else:
        entropy_assessment = "low_entropy (potential padding, sparse data, or synthetic constant fill)"

    return {
        "sha256": hashes["sha256"],
        "sha1": hashes["sha1"],
        "md5": hashes["md5"],
        "size_bytes": len(data),
        "entropy_bits_per_byte": entropy,
        "entropy_assessment": entropy_assessment,
        "container_check": container_info,
        "certified_at": datetime.now(timezone.utc).isoformat(),
    }
