import hashlib
import io
from backend.integrity import (
    calculate_shannon_entropy,
    compute_hashes,
    generate_forensic_integrity_record,
    inspect_container_structure,
)


def test_compute_hashes():
    test_data = b"Forensic Investigation Integrity Check 2026"
    hashes = compute_hashes(test_data)

    expected_sha256 = hashlib.sha256(test_data).hexdigest()
    expected_md5 = hashlib.md5(test_data).hexdigest()

    assert hashes["sha256"] == expected_sha256
    assert hashes["md5"] == expected_md5
    assert len(hashes["sha256"]) == 64
    assert len(hashes["md5"]) == 32


def test_calculate_shannon_entropy():
    # Uniform/repeated bytes should have 0 entropy
    zero_entropy = calculate_shannon_entropy(b"A" * 100)
    assert zero_entropy == 0.0

    # Diverse random bytes should have high entropy
    diverse_bytes = bytes(range(256))
    high_entropy = calculate_shannon_entropy(diverse_bytes)
    assert high_entropy == 8.0


def test_inspect_container_structure_jpeg():
    # Valid JPEG SOI (\xff\xd8) and EOI (\xff\xd9)
    clean_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
    result = inspect_container_structure(clean_jpeg, filename="test.jpg")
    assert result["valid_magic"] is True
    assert result["has_trailing_payload"] is False
    assert result["status"] == "intact"

    # JPEG with injected trailing bytes (> 128 bytes)
    tampered_jpeg = clean_jpeg + (b"HIDDEN_PAYLOAD_EXTRA_DATA" * 10)
    tampered_result = inspect_container_structure(tampered_jpeg, filename="test.jpg")
    assert tampered_result["valid_magic"] is True
    assert tampered_result["has_trailing_payload"] is True
    assert tampered_result["status"] == "trailing_bytes_detected"


def test_generate_forensic_integrity_record():
    data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\x00IEND\xaeB`\x82"
    record = generate_forensic_integrity_record(data, filename="sample.png", mime_type="image/png")

    assert "sha256" in record
    assert "md5" in record
    assert record["size_bytes"] == len(data)
    assert record["entropy_bits_per_byte"] > 0
    assert "container_check" in record
    assert record["container_check"]["valid_magic"] is True
    assert record["certified_at"].endswith("Z") or "+00:00" in record["certified_at"]
