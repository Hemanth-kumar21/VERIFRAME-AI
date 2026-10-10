from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "results.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

Base = declarative_base()


class ResultRecord(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    verdict = Column(String, nullable=False)
    evidence_strength = Column(String, nullable=False)
    agreement = Column(String, nullable=False)
    tool_summaries = Column(JSON, default=dict)
    trace = Column(JSON, default=list)
    limitations = Column(JSON, default=list)
    explanation = Column(JSON, default=dict)
    mode = Column(String, nullable=False)
    llm_provider_info = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_now_utc)


class UserReport(Base):
    __tablename__ = "user_reports"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False)
    comment = Column(String, nullable=False, default="")
    created_at = Column(DateTime, default=_now_utc)


class InvestigationCaseRecord(Base):
    __tablename__ = "investigation_cases"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, default="")
    status = Column(String, default="open")  # open, in_review, concluded, archived
    priority = Column(String, default="normal")  # low, normal, high, urgent
    tags = Column(JSON, default=list)
    investigator = Column(String, default="Lead Forensic Specialist")
    notes = Column(JSON, default=list)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc)


class CaseItemRecord(Base):
    __tablename__ = "case_items"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, index=True, nullable=False)
    token = Column(String, index=True, nullable=False)
    item_type = Column(String, default="image")  # image | video
    label = Column(String, default="")
    sha256 = Column(String, default="")
    notes = Column(String, default="")
    added_at = Column(DateTime, default=_now_utc)


class CaseAuditRecord(Base):
    __tablename__ = "case_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, index=True, nullable=False)
    action = Column(String, nullable=False)
    actor = Column(String, default="Investigator")
    summary = Column(String, default="")
    metadata_json = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=_now_utc)


engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)


def save_result(payload: dict) -> dict:
    with SessionLocal() as session:
        tool_summaries = dict(payload.get("tool_summaries") or {})
        if "integrity" in payload and "integrity" not in tool_summaries:
            tool_summaries["integrity"] = payload["integrity"]
        if "nemotron" in payload and "nemotron" not in tool_summaries:
            tool_summaries["nemotron"] = payload["nemotron"]
        if "ai_content_detection" in payload and "ai_content_detection" not in tool_summaries:
            tool_summaries["ai_content_detection"] = payload["ai_content_detection"]

        existing = session.query(ResultRecord).filter(ResultRecord.token == payload["token"]).first()
        if existing:
            existing.verdict = payload["verdict"]
            existing.evidence_strength = payload["evidence_strength"]
            existing.agreement = payload["agreement"]
            existing.tool_summaries = tool_summaries
            existing.trace = payload.get("trace", [])
            existing.limitations = payload.get("limitations", [])
            existing.explanation = payload.get("explanation", {})
            existing.mode = payload.get("mode", "fixed pipeline")
            existing.llm_provider_info = payload.get("llm_provider_info", {})
            session.commit()
            return {"id": existing.id, "token": existing.token}

        record = ResultRecord(
            token=payload["token"],
            verdict=payload["verdict"],
            evidence_strength=payload["evidence_strength"],
            agreement=payload["agreement"],
            tool_summaries=tool_summaries,
            trace=payload.get("trace", []),
            limitations=payload.get("limitations", []),
            explanation=payload.get("explanation", {}),
            mode=payload.get("mode", "fixed pipeline"),
            llm_provider_info=payload.get("llm_provider_info", {}),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return {"id": record.id, "token": record.token}


def get_result_by_token(token: str) -> dict | None:
    with SessionLocal() as session:
        record = session.query(ResultRecord).filter(ResultRecord.token == token).first()
        if not record:
            return None
        summaries = record.tool_summaries if isinstance(record.tool_summaries, dict) else {}
        integrity = summaries.get("integrity")
        return {
            "token": record.token,
            "verdict": record.verdict,
            "evidence_strength": record.evidence_strength,
            "agreement": record.agreement,
            "tool_summaries": summaries,
            "integrity": integrity,
            "nemotron": summaries.get("nemotron"),
            "ai_content_detection": summaries.get("ai_content_detection"),
            "trace": record.trace,
            "limitations": record.limitations,
            "explanation": record.explanation,
            "mode": record.mode,
            "llm_provider_info": record.llm_provider_info,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }


def save_report(token: str, category: str, comment: str) -> None:
    with SessionLocal() as session:
        session.add(UserReport(token=token, category=category, comment=comment))
        session.commit()


def get_insights() -> dict:
    with SessionLocal() as session:
        records = session.query(ResultRecord.mode, ResultRecord.llm_provider_info).all()
        total = len(records)
        verdict_distribution = {
            "Likely AI": session.query(ResultRecord).filter(ResultRecord.verdict == "Likely AI").count(),
            "Inconclusive": session.query(ResultRecord).filter(ResultRecord.verdict == "Inconclusive").count(),
            "No AI signs found": session.query(ResultRecord).filter(ResultRecord.verdict == "No AI signs found").count(),
        }
        mode_distribution: dict[str, int] = {}
        latencies = []
        for mode, provider_info in records:
            mode_name = mode or "not reported"
            mode_distribution[mode_name] = mode_distribution.get(mode_name, 0) + 1
            if isinstance(provider_info, dict):
                latency = provider_info.get("latency_ms")
                if isinstance(latency, (int, float)) and latency >= 0:
                    latencies.append(float(latency))
        wrong_result_reports = (
            session.query(UserReport)
            .filter(UserReport.category.in_(("incorrect_verdict", "incorrect_evidence")))
            .count()
        )
        total_cases = session.query(InvestigationCaseRecord).count()
        return {
            "total_analyses": total,
            "verdict_distribution": verdict_distribution,
            "inconclusive_share": round((verdict_distribution["Inconclusive"] / total) * 100, 2) if total else 0,
            "mode_distribution": mode_distribution,
            "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "wrong_result_reports": wrong_result_reports,
            "total_investigation_cases": total_cases,
        }


# ==============================================================================
# INVESTIGATION WORKSPACE & CASE MANAGEMENT
# ==============================================================================


def create_case(
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    priority: str = "normal",
    investigator: str = "Lead Forensic Specialist",
    case_id: str | None = None,
) -> dict[str, Any]:
    with SessionLocal() as session:
        if not case_id:
            case_id = f"CASE-{_now_utc().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

        record = InvestigationCaseRecord(
            case_id=case_id,
            title=title.strip() or "Untitled Investigation",
            description=description.strip(),
            status="open",
            priority=priority,
            tags=tags or [],
            investigator=investigator.strip(),
            notes=[
                {
                    "id": uuid.uuid4().hex[:8],
                    "timestamp": _now_utc().isoformat(),
                    "author": investigator,
                    "content": f"Case opened: '{title.strip()}' initialized in workspace.",
                }
            ],
            created_at=_now_utc(),
            updated_at=_now_utc(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        audit = CaseAuditRecord(
            case_id=case_id,
            action="case_created",
            actor=investigator,
            summary=f"Case {case_id} initialized: {title}",
            metadata_json={"priority": priority, "tags": tags or []},
        )
        session.add(audit)
        session.commit()

        return _serialize_case(record)


def get_case(case_id: str) -> dict[str, Any] | None:
    with SessionLocal() as session:
        record = (
            session.query(InvestigationCaseRecord)
            .filter(InvestigationCaseRecord.case_id == case_id)
            .first()
        )
        if not record:
            return None
        return _serialize_case(record)


def list_cases(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        query = session.query(InvestigationCaseRecord)
        if status:
            query = query.filter(InvestigationCaseRecord.status == status)
        records = (
            query.order_by(InvestigationCaseRecord.updated_at.desc())
            .limit(limit)
            .all()
        )
        results = []
        for r in records:
            case_dict = _serialize_case(r)
            item_count = (
                session.query(CaseItemRecord)
                .filter(CaseItemRecord.case_id == r.case_id)
                .count()
            )
            case_dict["item_count"] = item_count
            results.append(case_dict)
        return results


def update_case(case_id: str, updates: dict[str, Any], actor: str = "Investigator") -> dict[str, Any] | None:
    with SessionLocal() as session:
        record = (
            session.query(InvestigationCaseRecord)
            .filter(InvestigationCaseRecord.case_id == case_id)
            .first()
        )
        if not record:
            return None

        allowed = {"title", "description", "status", "priority", "tags", "investigator"}
        changes = {}
        for key, value in updates.items():
            if key in allowed and getattr(record, key) != value:
                changes[key] = {"old": getattr(record, key), "new": value}
                setattr(record, key, value)

        record.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(record)

        if changes:
            audit = CaseAuditRecord(
                case_id=case_id,
                action="case_updated",
                actor=actor,
                summary=f"Updated fields: {', '.join(changes.keys())}",
                metadata_json=changes,
            )
            session.add(audit)
            session.commit()

        return _serialize_case(record)


def add_case_note(case_id: str, author: str, content: str) -> dict[str, Any] | None:
    with SessionLocal() as session:
        record = (
            session.query(InvestigationCaseRecord)
            .filter(InvestigationCaseRecord.case_id == case_id)
            .first()
        )
        if not record:
            return None

        current_notes = list(record.notes or [])
        note_entry = {
            "id": uuid.uuid4().hex[:8],
            "timestamp": _now_utc().isoformat(),
            "author": author or "Investigator",
            "content": content.strip(),
        }
        current_notes.append(note_entry)
        record.notes = current_notes
        record.updated_at = _now_utc()
        session.commit()
        session.refresh(record)

        audit = CaseAuditRecord(
            case_id=case_id,
            action="note_added",
            actor=author,
            summary=f"Added investigator note ({len(content.strip())} chars)",
            metadata_json={"note_id": note_entry["id"]},
        )
        session.add(audit)
        session.commit()

        return _serialize_case(record)


def attach_item_to_case(
    case_id: str,
    token: str,
    item_type: str = "image",
    label: str = "",
    notes: str = "",
    actor: str = "Investigator",
) -> dict[str, Any]:
    with SessionLocal() as session:
        case = (
            session.query(InvestigationCaseRecord)
            .filter(InvestigationCaseRecord.case_id == case_id)
            .first()
        )
        if not case:
            raise ValueError(f"Case '{case_id}' does not exist.")

        # Check if already attached
        existing = (
            session.query(CaseItemRecord)
            .filter(CaseItemRecord.case_id == case_id, CaseItemRecord.token == token)
            .first()
        )
        if existing:
            return {
                "id": existing.id,
                "case_id": existing.case_id,
                "token": existing.token,
                "status": "already_attached",
            }

        # Look up result for metadata & sha256
        res = session.query(ResultRecord).filter(ResultRecord.token == token).first()
        sha256 = ""
        if res and isinstance(res.tool_summaries, dict):
            integ = res.tool_summaries.get("integrity")
            if isinstance(integ, dict):
                sha256 = str(integ.get("sha256") or "")

        item = CaseItemRecord(
            case_id=case_id,
            token=token,
            item_type=item_type,
            label=label.strip() or f"Evidence Item ({token[:8]})",
            sha256=sha256,
            notes=notes.strip(),
            added_at=_now_utc(),
        )
        session.add(item)
        case.updated_at = _now_utc()
        session.commit()
        session.refresh(item)

        audit = CaseAuditRecord(
            case_id=case_id,
            action="item_attached",
            actor=actor,
            summary=f"Attached {item_type} evidence token '{token}'",
            metadata_json={"token": token, "item_type": item_type, "label": item.label},
        )
        session.add(audit)
        session.commit()

        return {
            "id": item.id,
            "case_id": item.case_id,
            "token": item.token,
            "item_type": item.item_type,
            "label": item.label,
            "sha256": item.sha256,
            "notes": item.notes,
            "added_at": item.added_at.isoformat() if item.added_at else None,
        }


def remove_item_from_case(case_id: str, token: str, actor: str = "Investigator") -> bool:
    with SessionLocal() as session:
        item = (
            session.query(CaseItemRecord)
            .filter(CaseItemRecord.case_id == case_id, CaseItemRecord.token == token)
            .first()
        )
        if not item:
            return False
        session.delete(item)

        case = (
            session.query(InvestigationCaseRecord)
            .filter(InvestigationCaseRecord.case_id == case_id)
            .first()
        )
        if case:
            case.updated_at = datetime.utcnow()

        audit = CaseAuditRecord(
            case_id=case_id,
            action="item_removed",
            actor=actor,
            summary=f"Detached evidence token '{token}' from case",
            metadata_json={"token": token},
        )
        session.add(audit)
        session.commit()
        return True


def get_case_items(case_id: str) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        items = (
            session.query(CaseItemRecord)
            .filter(CaseItemRecord.case_id == case_id)
            .order_by(CaseItemRecord.added_at.asc())
            .all()
        )
        results = []
        for it in items:
            # Join with result data if present
            res = session.query(ResultRecord).filter(ResultRecord.token == it.token).first()
            item_dict = {
                "id": it.id,
                "case_id": it.case_id,
                "token": it.token,
                "item_type": it.item_type,
                "label": it.label,
                "sha256": it.sha256,
                "notes": it.notes,
                "added_at": it.added_at.isoformat() if it.added_at else None,
                "result": None,
            }
            if res:
                item_dict["result"] = {
                    "verdict": res.verdict,
                    "evidence_strength": res.evidence_strength,
                    "agreement": res.agreement,
                    "mode": res.mode,
                    "created_at": res.created_at.isoformat() if res.created_at else None,
                    "tool_summaries": res.tool_summaries,
                }
            results.append(item_dict)
        return results


def log_case_audit(
    case_id: str,
    action: str,
    summary: str,
    actor: str = "Investigator",
    metadata: dict[str, Any] | None = None,
) -> None:
    with SessionLocal() as session:
        audit = CaseAuditRecord(
            case_id=case_id,
            action=action,
            actor=actor,
            summary=summary,
            metadata_json=metadata or {},
        )
        session.add(audit)
        session.commit()


def get_case_audit_logs(case_id: str, limit: int = 100) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        records = (
            session.query(CaseAuditRecord)
            .filter(CaseAuditRecord.case_id == case_id)
            .order_by(CaseAuditRecord.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "case_id": r.case_id,
                "action": r.action,
                "actor": r.actor,
                "summary": r.summary,
                "metadata": r.metadata_json,
                "timestamp": r.timestamp.isoformat() + "Z" if r.timestamp else None,
            }
            for r in records
        ]


def _serialize_case(record: InvestigationCaseRecord) -> dict[str, Any]:
    return {
        "case_id": record.case_id,
        "title": record.title,
        "description": record.description,
        "status": record.status,
        "priority": record.priority,
        "tags": record.tags or [],
        "investigator": record.investigator,
        "notes": record.notes or [],
        "created_at": record.created_at.isoformat() + "Z" if record.created_at else None,
        "updated_at": record.updated_at.isoformat() + "Z" if record.updated_at else None,
    }
