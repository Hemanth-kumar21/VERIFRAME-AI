from fastapi.testclient import TestClient
from backend.db import create_case, get_case, list_cases, save_result
from backend.main import app

client = TestClient(app)


def test_create_and_get_case():
    case = create_case(
        title="Test Investigation Alpha",
        description="Forensic investigation into viral image.",
        tags=["social-media", "tampering"],
        priority="high",
        investigator="Specialist Agent",
    )

    assert "case_id" in case
    assert case["title"] == "Test Investigation Alpha"
    assert case["status"] == "open"
    assert case["priority"] == "high"

    fetched = get_case(case["case_id"])
    assert fetched is not None
    assert fetched["case_id"] == case["case_id"]
    assert len(fetched["notes"]) >= 1


def test_cases_api_lifecycle():
    # 1. Create case via API
    resp = client.post(
        "/api/cases",
        json={
            "title": "API Case Test",
            "description": "Integration test for case lifecycle.",
            "tags": ["deepfake"],
            "priority": "normal",
        },
    )
    assert resp.status_code == 200
    created = resp.json()
    case_id = created["case_id"]

    # 2. List cases
    list_resp = client.get("/api/cases")
    assert list_resp.status_code == 200
    cases_list = list_resp.json()["cases"]
    assert any(c["case_id"] == case_id for c in cases_list)

    # 3. Add note
    note_resp = client.post(
        f"/api/cases/{case_id}/notes",
        json={"author": "Lead Examiner", "content": "Initial evidence acquired and hashed."},
    )
    assert note_resp.status_code == 200
    assert any("Initial evidence" in n["content"] for n in note_resp.json()["notes"])

    # 4. Attach an item
    import uuid
    dummy_token = f"test_item_{uuid.uuid4().hex[:8]}"
    save_result({
        "token": dummy_token,
        "verdict": "Likely AI",
        "evidence_strength": "strong",
        "agreement": "high",
        "tool_summaries": {
            "integrity": {"sha256": "abcdef1234567890", "entropy_bits_per_byte": 7.8},
        },
        "mode": "fixed pipeline",
    })

    attach_resp = client.post(
        f"/api/cases/{case_id}/attach",
        json={
            "token": dummy_token,
            "item_type": "image",
            "label": "Primary Evidence #1",
            "notes": "Verified source hash.",
        },
    )
    assert attach_resp.status_code == 200

    # 5. Get case with correlation
    get_resp = client.get(f"/api/cases/{case_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert len(data["items"]) >= 1
    assert data["items"][0]["token"] == dummy_token
    assert "correlation" in data
    assert data["correlation"]["total_items"] >= 1

    # 6. Check report HTML endpoint
    report_resp = client.get(f"/api/cases/{case_id}/report")
    assert report_resp.status_code == 200
    assert "text/html" in report_resp.headers["content-type"]
    assert "Investigation Dossier" in report_resp.text
    assert case_id in report_resp.text

    # 7. Check export.json endpoint
    export_resp = client.get(f"/api/cases/{case_id}/export.json")
    assert export_resp.status_code == 200
    assert export_resp.json()["case"]["case_id"] == case_id

    # 8. Check single item dossier endpoint
    dossier_resp = client.get(f"/api/result/{dummy_token}/dossier")
    assert dossier_resp.status_code == 200
    assert "text/html" in dossier_resp.headers["content-type"]
    assert "Digital Forensic Evidence Dossier" in dossier_resp.text
    assert dummy_token in dossier_resp.text
