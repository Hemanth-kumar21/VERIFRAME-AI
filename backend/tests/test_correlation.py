from backend.correlation import correlate_case_evidence


def test_correlate_empty_evidence():
    result = correlate_case_evidence([])
    assert result["total_items"] == 0
    assert result["divergence_status"] == "no_evidence"
    assert len(result["investigative_leads"]) > 0


def test_correlate_consistent_evidence():
    items = [
        {
            "token": "tok_1",
            "label": "Front Camera Still",
            "item_type": "image",
            "result": {
                "verdict": "No AI signs found",
                "evidence_strength": "moderate",
                "tool_summaries": {
                    "metadata": {"exif": {"Make": "Sony", "Model": "A7IV", "DateTimeOriginal": "2026:03:01 10:00:00"}},
                    "integrity": {"sha256": "1111", "container_check": {"has_trailing_payload": False}},
                },
            },
        },
        {
            "token": "tok_2",
            "label": "Secondary Angle",
            "item_type": "image",
            "result": {
                "verdict": "No AI signs found",
                "evidence_strength": "moderate",
                "tool_summaries": {
                    "metadata": {"exif": {"Make": "Sony", "Model": "A7IV", "DateTimeOriginal": "2026:03:01 10:02:00"}},
                    "integrity": {"sha256": "2222", "container_check": {"has_trailing_payload": False}},
                },
            },
        },
    ]

    analysis = correlate_case_evidence(items)
    assert analysis["total_items"] == 2
    assert analysis["divergence_status"] == "coherent_organic_cluster"
    assert len(analysis["contradictions"]) == 0
    assert len(analysis["timeline"]) == 2
    assert len(analysis["graph"]["nodes"]) >= 2


def test_correlate_verdict_divergence_selective_manipulation():
    items = [
        {
            "token": "tok_real",
            "label": "Original Press Photo",
            "item_type": "image",
            "result": {
                "verdict": "No AI signs found",
                "evidence_strength": "strong",
                "tool_summaries": {
                    "integrity": {"sha256": "aaaa", "container_check": {"has_trailing_payload": False}},
                },
            },
        },
        {
            "token": "tok_fake",
            "label": "Viral Social Media Variant",
            "item_type": "image",
            "result": {
                "verdict": "Likely AI",
                "evidence_strength": "strong",
                "tool_summaries": {
                    "integrity": {"sha256": "bbbb", "container_check": {"has_trailing_payload": False}},
                },
            },
        },
    ]

    analysis = correlate_case_evidence(items)
    assert analysis["divergence_status"] == "selective_manipulation_suspected"
    # Should flag critical contradiction for divergence
    has_divergence_flag = any(c["type"] == "VERDICT_DIVERGENCE" for c in analysis["contradictions"])
    assert has_divergence_flag is True
    # Priority lead should be generated
    assert any("selective manipulation" in lead.lower() or "priority lead" in lead.lower() for lead in analysis["investigative_leads"])


def test_correlate_container_tampering():
    items = [
        {
            "token": "tok_steg",
            "label": "Suspicious Meme Image",
            "item_type": "image",
            "result": {
                "verdict": "Inconclusive",
                "tool_summaries": {
                    "integrity": {
                        "sha256": "cccc",
                        "container_check": {"has_trailing_payload": True, "trailing_bytes": 1024},
                    },
                },
            },
        }
    ]

    analysis = correlate_case_evidence(items)
    assert any(c["type"] == "CONTAINER_INTEGRITY_TAMPER_FLAG" for c in analysis["contradictions"])
