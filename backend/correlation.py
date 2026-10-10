from __future__ import annotations

from typing import Any


def correlate_case_evidence(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Correlate multiple evidence items in an investigation case.

    Evaluates timeline chronology, camera sensor consistency, software markers,
    divergent authenticity verdicts, and structural container anomalies.
    Returns an explainable correlation matrix, graph nodes/edges, and investigative leads.
    """
    if not items:
        return {
            "total_items": 0,
            "timeline": [],
            "verdict_summary": {},
            "divergence_status": "no_evidence",
            "contradictions": [],
            "graph": {"nodes": [], "edges": []},
            "investigative_leads": ["Add evidence items to this case to initiate cross-media correlation."],
        }

    # 1. Extract forensic traits per item
    timeline_entries = []
    verdicts = {}
    cameras = set()
    softwares = set()
    contradictions = []
    nodes = []
    edges = []

    for idx, item in enumerate(items):
        token = item.get("token", f"item_{idx}")
        label = item.get("label") or f"Evidence #{idx + 1}"
        result = item.get("result") or {}
        tool_summaries = result.get("tool_summaries") or {}
        integ = tool_summaries.get("integrity") or {}

        verdict = result.get("verdict") or "Pending"
        strength = result.get("evidence_strength") or "unknown"
        verdicts[verdict] = verdicts.get(verdict, 0) + 1

        # Extract metadata
        meta = tool_summaries.get("metadata") or {}
        exif = meta.get("exif") if isinstance(meta, dict) else {}
        if not isinstance(exif, dict):
            exif = {}

        camera_make = exif.get("Make") or exif.get("LensMake")
        camera_model = exif.get("Model") or exif.get("LensModel")
        camera_desc = f"{camera_make} {camera_model}".strip() if (camera_make or camera_model) else None
        if camera_desc:
            cameras.add(camera_desc)

        software_desc = exif.get("Software") or exif.get("ProcessingSoftware")
        if software_desc:
            softwares.add(str(software_desc).strip())

        # Timestamp identification
        timestamp_str = (
            exif.get("DateTimeOriginal")
            or exif.get("CreateDate")
            or result.get("created_at")
            or item.get("added_at")
            or "Unknown"
        )

        timeline_entries.append({
            "token": token,
            "label": label,
            "timestamp": timestamp_str,
            "verdict": verdict,
            "item_type": item.get("item_type", "image"),
            "camera": camera_desc,
            "software": software_desc,
            "sha256": item.get("sha256") or integ.get("sha256") or "N/A",
        })

        # Add node for evidence
        node_id = f"item_{token[:8]}"
        nodes.append({
            "id": node_id,
            "label": label,
            "type": "evidence",
            "verdict": verdict,
            "media_type": item.get("item_type", "image"),
        })

        if camera_desc:
            cam_node_id = f"cam_{camera_desc.replace(' ', '_')}"
            if not any(n["id"] == cam_node_id for n in nodes):
                nodes.append({"id": cam_node_id, "label": camera_desc, "type": "camera"})
            edges.append({"from": node_id, "to": cam_node_id, "relationship": "captured_by"})

        if software_desc:
            soft_node_id = f"soft_{str(software_desc)[:16].replace(' ', '_')}"
            if not any(n["id"] == soft_node_id for n in nodes):
                nodes.append({"id": soft_node_id, "label": str(software_desc), "type": "software"})
            edges.append({"from": node_id, "to": soft_node_id, "relationship": "processed_with"})

        # Check for container anomalies (trailing bytes)
        container_check = integ.get("container_check") if isinstance(integ, dict) else {}
        if isinstance(container_check, dict) and container_check.get("has_trailing_payload"):
            trailing = container_check.get("trailing_bytes", 0)
            contradictions.append({
                "type": "CONTAINER_INTEGRITY_TAMPER_FLAG",
                "severity": "high",
                "affected_items": [token],
                "description": (
                    f"Item '{label}' contains {trailing} trailing bytes past its container EOF marker. "
                    "This indicates possible steganographic injection or concatenated payload."
                ),
            })

    # 2. Cross-item verdict divergence check
    has_ai = verdicts.get("Likely AI", 0) > 0
    has_non_ai = verdicts.get("No AI signs found", 0) > 0
    has_inconclusive = verdicts.get("Inconclusive", 0) > 0

    if has_ai and has_non_ai:
        divergence_status = "selective_manipulation_suspected"
        contradictions.append({
            "type": "VERDICT_DIVERGENCE",
            "severity": "critical",
            "affected_items": [i["token"] for i in items],
            "description": (
                "Case contains both 'Likely AI' and 'No AI signs found' items. "
                "This divergence strongly suggests selective manipulation, localized deepfake splicing, "
                "or combination of authentic source footage with synthetic assets."
            ),
        })
    elif has_ai:
        divergence_status = "coherent_synthetic_cluster"
    elif has_non_ai and not has_inconclusive:
        divergence_status = "coherent_organic_cluster"
    else:
        divergence_status = "mixed_or_inconclusive"

    # 3. Camera sensor discrepancies
    if len(cameras) > 1 and len(items) >= 2:
        contradictions.append({
            "type": "SENSOR_PROFILE_MISMATCH",
            "severity": "medium",
            "affected_items": [i["token"] for i in items if i.get("camera")],
            "description": (
                f"Multiple camera profiles identified ({', '.join(cameras)}). "
                "If items depict the same concurrent scene from a single purported recording device, "
                "this indicates mismatched sources or spliced media."
            ),
        })

    # 4. Generate forensic investigation leads
    leads = []
    if divergence_status == "selective_manipulation_suspected":
        leads.append(
            "Priority Lead: Perform frame-by-frame and tile cross-comparison between the 'Likely AI' "
            "and 'No AI' media items to isolate exact boundaries where synthetic content was introduced."
        )
    if softwares:
        leads.append(
            f"Software Footprint Lead: Detected software tags ({', '.join(softwares)}). "
            "Verify whether these software packages are legitimate editing tools or synthetic post-processing suites."
        )
    if any(c["type"] == "CONTAINER_INTEGRITY_TAMPER_FLAG" for c in contradictions):
        leads.append(
            "Payload Lead: Extract and analyze the trailing byte payloads from flagged containers "
            "using raw hex inspection to check for hidden steganography or file concatenation."
        )
    if len(timeline_entries) >= 2:
        leads.append(
            f"Timeline Sequence: Verified chronological chain of {len(timeline_entries)} evidence assets. "
            "Examine timestamp intervals for gaps corresponding to unsubmitted media."
        )

    if not leads:
        leads.append("All evidence items in this case exhibit consistent forensic profiles. Continue monitoring.")

    # Link items sequentially in graph
    for idx in range(len(timeline_entries) - 1):
        edges.append({
            "from": f"item_{timeline_entries[idx]['token'][:8]}",
            "to": f"item_{timeline_entries[idx + 1]['token'][:8]}",
            "relationship": "precedes_in_timeline",
        })

    return {
        "total_items": len(items),
        "timeline": timeline_entries,
        "verdict_summary": verdicts,
        "divergence_status": divergence_status,
        "detected_cameras": list(cameras),
        "detected_softwares": list(softwares),
        "contradictions": contradictions,
        "graph": {"nodes": nodes, "edges": edges},
        "investigative_leads": leads,
    }
