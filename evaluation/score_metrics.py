"""Compute evaluation metrics from pipeline results."""

import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

RESULTS_DIR = Path(__file__).parent / "results"
SIMILARITY_THRESHOLD = 0.6


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _question_matches(predicted: str, gold: str) -> bool:
    """Check if a predicted question semantically matches a gold question."""
    return _similar(predicted, gold) > SIMILARITY_THRESHOLD


def score_red_flag_coverage(result: dict) -> float:
    """RedFlagCoverage = matched red-flag suggestions / total gold red-flags."""
    red_flags = result.get("red_flag_questions", [])
    suggestions = result.get("suggested_questions", [])

    if not red_flags:
        return 1.0

    predicted_texts = [q["question"] for q in suggestions]
    matched = 0
    for rf in red_flags:
        rf_text = rf["question"]
        if any(_question_matches(p, rf_text) for p in predicted_texts):
            matched += 1

    return matched / len(red_flags)


def score_history_completeness(result: dict) -> float:
    """HistoryCompleteness = covered domains / expected domains."""
    expected = result.get("expected_domains", [])
    if not expected:
        return 1.0

    # Domains from encounter state + suggestion domains
    covered = set()
    encounter = result.get("encounter_state", {})
    for d in encounter.get("domains_covered", []):
        covered.add(d.lower())

    for q in result.get("suggested_questions", []):
        covered.add(q.get("domain", "").lower())

    matched = sum(
        1 for ed in expected
        if any(_similar(ed.lower(), cd) > SIMILARITY_THRESHOLD for cd in covered)
    )

    return matched / len(expected)


def score_question_relevance(result: dict) -> float:
    """QuestionRelevance = matched suggestions / total suggestions."""
    suggestions = result.get("suggested_questions", [])
    gold = result.get("gold_standard_questions", [])

    if not suggestions:
        return 0.0

    gold_texts = [g["question"] for g in gold]
    matched = sum(
        1 for s in suggestions
        if any(_question_matches(s["question"], g) for g in gold_texts)
    )

    return matched / len(suggestions)


def score_consult_accuracy(result: dict) -> float:
    """ConsultAccuracy = correct referral recommendation (binary + partial)."""
    predicted = result.get("consult_decision", {})
    expected = result.get("expected_consult", {})

    if not expected:
        return 1.0

    score = 0.0

    # Specialty match (0.5 weight)
    pred_specialty = predicted.get("specialty", "").lower()
    exp_specialty = expected.get("specialty", "").lower()
    if _similar(pred_specialty, exp_specialty) > 0.5 or pred_specialty == exp_specialty:
        score += 0.5

    # Urgency match (0.5 weight)
    pred_urgency = predicted.get("urgency", "").lower()
    exp_urgency = expected.get("urgency", "").lower()
    if pred_urgency == exp_urgency:
        score += 0.5
    elif (  # Adjacent urgency levels get partial credit
        (pred_urgency in ("emergent", "urgent") and exp_urgency in ("emergent", "urgent"))
        or (pred_urgency in ("routine", "not_needed") and exp_urgency in ("routine", "not_needed"))
    ):
        score += 0.25

    return score


def compute_all_metrics(results: list[dict]) -> dict:
    """Compute all metrics across all vignettes."""
    successful = [r for r in results if "error" not in r]
    if not successful:
        return {"error": "No successful results to score."}

    metrics = {
        "n_vignettes": len(successful),
        "n_failed": len(results) - len(successful),
    }

    # Per-vignette scores
    rf_scores = []
    hc_scores = []
    qr_scores = []
    ca_scores = []
    latencies = []

    per_vignette = []
    for r in successful:
        rf = score_red_flag_coverage(r)
        hc = score_history_completeness(r)
        qr = score_question_relevance(r)
        ca = score_consult_accuracy(r)
        lat = r.get("latency_seconds", 0)

        rf_scores.append(rf)
        hc_scores.append(hc)
        qr_scores.append(qr)
        ca_scores.append(ca)
        latencies.append(lat)

        per_vignette.append({
            "id": r["vignette_id"],
            "specialty": r["specialty"],
            "red_flag_coverage": round(rf, 3),
            "history_completeness": round(hc, 3),
            "question_relevance": round(qr, 3),
            "consult_accuracy": round(ca, 3),
            "latency_seconds": round(lat, 2),
        })

    # Aggregate
    metrics["aggregate"] = {
        "red_flag_coverage": {
            "mean": round(float(np.mean(rf_scores)), 3),
            "std": round(float(np.std(rf_scores)), 3),
            "min": round(float(np.min(rf_scores)), 3),
            "target": 0.80,
            "met": float(np.mean(rf_scores)) >= 0.80,
        },
        "history_completeness": {
            "mean": round(float(np.mean(hc_scores)), 3),
            "std": round(float(np.std(hc_scores)), 3),
            "min": round(float(np.min(hc_scores)), 3),
            "target": 0.75,
            "met": float(np.mean(hc_scores)) >= 0.75,
        },
        "question_relevance": {
            "mean": round(float(np.mean(qr_scores)), 3),
            "std": round(float(np.std(qr_scores)), 3),
            "min": round(float(np.min(qr_scores)), 3),
            "target": 0.60,
            "met": float(np.mean(qr_scores)) >= 0.60,
        },
        "consult_accuracy": {
            "mean": round(float(np.mean(ca_scores)), 3),
            "std": round(float(np.std(ca_scores)), 3),
            "min": round(float(np.min(ca_scores)), 3),
        },
        "latency": {
            "p50": round(float(np.percentile(latencies, 50)), 2),
            "p95": round(float(np.percentile(latencies, 95)), 2),
            "mean": round(float(np.mean(latencies)), 2),
        },
    }

    metrics["per_vignette"] = per_vignette

    return metrics


def main():
    results_path = RESULTS_DIR / "evaluation_results.json"
    if not results_path.exists():
        print(f"No results file found at {results_path}")
        print("Run run_evaluation.py first.")
        sys.exit(1)

    with open(results_path) as f:
        results = json.load(f)

    metrics = compute_all_metrics(results)

    # Save metrics
    metrics_path = RESULTS_DIR / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    # Print summary
    print("=" * 60)
    print("OPD Question Copilot — Evaluation Metrics")
    print("=" * 60)
    agg = metrics.get("aggregate", {})

    for name, data in agg.items():
        if name == "latency":
            print(f"\n  Latency:")
            print(f"    p50: {data['p50']}s  |  p95: {data['p95']}s  |  mean: {data['mean']}s")
        else:
            target = data.get("target", "—")
            met = data.get("met", "—")
            print(f"\n  {name}:")
            print(f"    mean: {data['mean']}  (std: {data['std']}, min: {data['min']})")
            if target != "—":
                status = "PASS" if met else "FAIL"
                print(f"    target: {target}  → {status}")

    print("\n" + "-" * 60)
    print("Per-vignette breakdown:")
    for pv in metrics.get("per_vignette", []):
        print(f"  [{pv['specialty']:15s}] RF={pv['red_flag_coverage']:.2f}  "
              f"HC={pv['history_completeness']:.2f}  QR={pv['question_relevance']:.2f}  "
              f"CA={pv['consult_accuracy']:.2f}  Lat={pv['latency_seconds']:.1f}s")

    print(f"\nMetrics saved to {metrics_path}")


if __name__ == "__main__":
    main()
