from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import JSON, Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

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
    created_at = Column(DateTime, default=datetime.utcnow)


class UserReport(Base):
    __tablename__ = "user_reports"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False)
    comment = Column(String, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)


def save_result(payload: dict) -> dict:
    from sqlalchemy.orm import Session

    with SessionLocal() as session:
        record = ResultRecord(
            token=payload["token"],
            verdict=payload["verdict"],
            evidence_strength=payload["evidence_strength"],
            agreement=payload["agreement"],
            tool_summaries=payload.get("tool_summaries", {}),
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
    from sqlalchemy.orm import Session

    with SessionLocal() as session:
        record = session.query(ResultRecord).filter(ResultRecord.token == token).first()
        if not record:
            return None
        return {
            "token": record.token,
            "verdict": record.verdict,
            "evidence_strength": record.evidence_strength,
            "agreement": record.agreement,
            "tool_summaries": record.tool_summaries,
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
    from sqlalchemy.orm import Session

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
        return {
            "total_analyses": total,
            "verdict_distribution": verdict_distribution,
            "inconclusive_share": round((verdict_distribution["Inconclusive"] / total) * 100, 2) if total else 0,
            "mode_distribution": mode_distribution,
            "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "wrong_result_reports": wrong_result_reports,
        }
