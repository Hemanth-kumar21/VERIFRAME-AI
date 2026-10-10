from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import agent, config, validation

RESULTS_PATH = ROOT / "benchmark" / "results.md"
GROUPS = ("real", "ai", "real_compressed", "ai_compressed")
IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
AI_VERDICT = "Likely AI"
REAL_VERDICT = "No AI signs found"
INCONCLUSIVE_VERDICT = "Inconclusive"


def compute_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    def group_summary(group_records: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(group_records)
        conclusive = sum(record["verdict"] != INCONCLUSIVE_VERDICT for record in group_records)
        correct = sum(
            record["verdict"] == (AI_VERDICT if record["expected_ai"] else REAL_VERDICT)
            for record in group_records
        )
        return {
            "total": total,
            "correct": correct,
            "accuracy_percent": round(correct / total * 100, 2) if total else None,
            "conclusive_accuracy_percent": (
                round(correct / conclusive * 100, 2) if conclusive else None
            ),
            "conclusive_coverage_percent": (
                round(conclusive / total * 100, 2) if total else None
            ),
            "inconclusive": total - conclusive,
            "inconclusive_rate_percent": (
                round((total - conclusive) / total * 100, 2) if total else None
            ),
            "likely_ai": sum(record["verdict"] == AI_VERDICT for record in group_records),
            "no_ai_signs": sum(record["verdict"] == REAL_VERDICT for record in group_records),
        }

    groups = {
        group: group_summary([record for record in records if record["group"] == group])
        for group in GROUPS
    }
    overall = group_summary(records)
    known_real = [record for record in records if not record["expected_ai"]]
    false_positives = sum(record["verdict"] == AI_VERDICT for record in known_real)
    return {
        "total": len(records),
        "accuracy_percent": overall["accuracy_percent"],
        "conclusive_accuracy_percent": overall["conclusive_accuracy_percent"],
        "conclusive_coverage_percent": overall["conclusive_coverage_percent"],
        "false_positives": false_positives,
        "false_positive_rate_percent": (
            round(false_positives / len(known_real) * 100, 2) if known_real else None
        ),
        "groups": groups,
        "verdict_counts": {
            verdict: sum(record["verdict"] == verdict for record in records)
            for verdict in (AI_VERDICT, REAL_VERDICT, INCONCLUSIVE_VERDICT)
        },
    }


def _configured_model_ids() -> list[str]:
    configured = (
        (config.DETECTOR_A_MODEL, config.DETECTOR_A_AI_LABEL),
        (config.DETECTOR_B_MODEL, config.DETECTOR_B_AI_LABEL),
        (config.DETECTOR_C_MODEL, config.DETECTOR_C_AI_LABEL),
    )
    return sorted({model_id for model_id, label in configured if model_id and label})


def _input_files(group: str) -> list[Path]:
    directory = ROOT / "benchmark" / group
    if not directory.is_dir():
        raise FileNotFoundError(
            f"Missing labeled folder: benchmark/{group}. See benchmark/README.md."
        )
    return sorted(path for path in directory.rglob("*") if path.is_file())


def _render_report(
    metrics: dict[str, Any],
    model_ids: list[str],
    skipped_files: int,
    validation_rejections: int,
) -> str:
    lines = [
        "# Benchmark results",
        "",
        f"Run time (UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "These measurements come from the actual configured image pipeline and only the local "
        "labeled files supplied in the benchmark folders. Inconclusive results count as incorrect "
        "for accuracy; conclusive accuracy is reported separately. This report is not calibration "
        "and does not establish detector accuracy outside this dataset.",
        "",
        f"- Distinct configured detector model IDs: {', '.join(model_ids)}",
        f"- Evaluated images: {metrics['total']}",
        f"- Skipped unsupported files: {skipped_files}",
        f"- Rejected images: {validation_rejections}",
        f"- Accuracy (inconclusive counts as incorrect): {metrics['accuracy_percent']}%",
        f"- Accuracy among conclusive results: {metrics['conclusive_accuracy_percent']}%",
        f"- Conclusive coverage: {metrics['conclusive_coverage_percent']}%",
        f"- False-positive rate on labeled real images: {metrics['false_positive_rate_percent']}%",
        f"- False positives: {metrics['false_positives']}",
        "",
        "| Labeled group | Images | Correct | Inconclusive | Inconclusive rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for group, values in metrics["groups"].items():
        lines.append(
            f"| {group} | {values['total']} | {values['correct']} | "
            f"{values['inconclusive']} | {values['inconclusive_rate_percent']}% |"
        )
    lines.extend(
        [
            "",
            "No source filenames or image contents are copied into this report. No calibration "
            "artifact is generated.",
            "",
        ]
    )
    return "\n".join(lines)


def run_benchmark() -> dict[str, Any]:
    model_ids = _configured_model_ids()
    if len(model_ids) < config.MIN_CONFIGURED_DETECTORS:
        raise RuntimeError(
            "Benchmark not run: configure at least two distinct detector model IDs and their "
            "verified AI-class labels first."
        )

    records: list[dict[str, Any]] = []
    skipped_files = 0
    validation_rejections = 0
    provider_status = {
        "available": False,
        "status": "offline",
        "tool_calling": "not_checked",
    }

    for group in GROUPS:
        expected_ai = group.startswith("ai")
        for path in _input_files(group):
            mime_type = IMAGE_MIME_TYPES.get(path.suffix.lower())
            if not mime_type:
                skipped_files += 1
                continue
            try:
                with path.open("rb") as source:
                    validation.validate_image_stream(source, path.name, mime_type)
            except ValueError:
                validation_rejections += 1
                continue

            result = agent.analyze_image(str(path), provider_status=provider_status)
            verdict = result.get("verdict")
            if verdict not in {AI_VERDICT, REAL_VERDICT, INCONCLUSIVE_VERDICT}:
                raise ValueError(f"Unexpected pipeline verdict for benchmark group {group}.")
            records.append(
                {
                    "group": group,
                    "expected_ai": expected_ai,
                    "verdict": verdict,
                }
            )

    if not records:
        raise RuntimeError("Benchmark not run: no valid supported images were found.")

    metrics = compute_metrics(records)
    report = _render_report(metrics, model_ids, skipped_files, validation_rejections)
    RESULTS_PATH.write_text(report, encoding="utf-8")
    return {
        "metrics": metrics,
        "detector_model_ids": model_ids,
        "skipped_unsupported_files": skipped_files,
        "rejected_images": validation_rejections,
        "results_path": str(RESULTS_PATH),
    }


def main() -> None:
    try:
        result = run_benchmark()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, indent=2))
    print(f"Measured results written to {RESULTS_PATH}. No calibration artifact was generated.")


if __name__ == "__main__":
    main()
