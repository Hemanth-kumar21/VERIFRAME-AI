from benchmark.evaluate import compute_metrics


def test_benchmark_metrics_keep_inconclusive_and_false_positives_explicit():
    records = [
        {"group": "real", "expected_ai": False, "verdict": "Likely AI"},
        {"group": "real", "expected_ai": False, "verdict": "Inconclusive"},
        {"group": "ai", "expected_ai": True, "verdict": "Likely AI"},
        {"group": "ai_compressed", "expected_ai": True, "verdict": "No AI signs found"},
    ]

    metrics = compute_metrics(records)

    assert metrics["total"] == 4
    assert metrics["accuracy_percent"] == 25.0
    assert metrics["conclusive_accuracy_percent"] == 33.33
    assert metrics["conclusive_coverage_percent"] == 75.0
    assert metrics["false_positives"] == 1
    assert metrics["false_positive_rate_percent"] == 50.0
    assert metrics["groups"]["real"]["inconclusive_rate_percent"] == 50.0
    assert metrics["groups"]["real_compressed"]["inconclusive_rate_percent"] is None
