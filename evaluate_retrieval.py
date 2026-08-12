"""Evaluate retrieval without calling the LLM and compare a keyword baseline."""

import json
import re
import time
from collections import defaultdict

from config import DISTANCE_THRESHOLD
from diagnose import retrieve_similar_incidents


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def keyword_rank(query, incidents):
    query_tokens = tokens(query)
    scored = []
    for incident in incidents:
        document = " ".join(str(value) for value in incident.values())
        scored.append((len(query_tokens & tokens(document)), incident["id"]))
    return [incident_id for _, incident_id in sorted(scored, reverse=True)]


def reciprocal_rank(ranked_ids, expected):
    try:
        return 1 / (ranked_ids.index(expected) + 1)
    except ValueError:
        return 0


def classification_metrics(tp, fp, tn, fn):
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": {
            "true_positive": tp,
            "false_positive": fp,
            "true_negative": tn,
            "false_negative": fn,
        },
    }


def main():
    cases = json.load(open("data/eval_set.json"))
    incidents = json.load(open("data/incidents.json"))
    positives = [case for case in cases if case["expected_incident"]]
    per_domain = defaultdict(lambda: {"correct": 0, "total": 0})
    recall_at_1 = recall_at_3 = 0
    reciprocal_ranks = []
    baseline_hits = 0
    latencies = []
    first_latency = None
    threshold_correct = 0
    tp = fp = tn = fn = 0

    for case in positives:
        started = time.perf_counter()
        ranked = retrieve_similar_incidents(case["trigger"], n=3)
        latencies.append((time.perf_counter() - started) * 1000)
        if first_latency is None:
            first_latency = latencies[-1]
        ranked_ids = [item["id"] for item in ranked]
        expected = case["expected_incident"]
        recall_at_1 += expected in ranked_ids[:1]
        recall_at_3 += expected in ranked_ids[:3]
        reciprocal_ranks.append(reciprocal_rank(ranked_ids, expected))
        per_domain[case["domain"]]["correct"] += expected in ranked_ids[:1]
        per_domain[case["domain"]]["total"] += 1
        baseline_hits += keyword_rank(case["trigger"], incidents)[0] == expected
        accepted = ranked[0]["distance"] <= DISTANCE_THRESHOLD
        threshold_correct += accepted
        tp += accepted
        fn += not accepted

    for case in (case for case in cases if not case["expected_incident"]):
        ranked = retrieve_similar_incidents(case["trigger"], n=1)
        incorrectly_matched = bool(ranked) and ranked[0]["distance"] <= DISTANCE_THRESHOLD
        fp += incorrectly_matched
        tn += not incorrectly_matched
        threshold_correct += not incorrectly_matched

    count = len(positives)
    classifier = classification_metrics(tp, fp, tn, fn)
    results = {
        "benchmark_cases": len(cases),
        "positive_cases": count,
        "novel_cases": len(cases) - count,
        "retrieval_recall_at_1": recall_at_1 / count,
        "retrieval_recall_at_3": recall_at_3 / count,
        "mean_reciprocal_rank": sum(reciprocal_ranks) / count,
        "keyword_baseline_accuracy": baseline_hits / count,
        "distance_threshold": DISTANCE_THRESHOLD,
        "threshold_classification_accuracy": threshold_correct / len(cases),
        "match_precision": classifier["precision"],
        "match_recall": classifier["recall"],
        "match_f1": classifier["f1"],
        "false_positive_rate": fp / (len(cases) - count),
        "confusion_matrix": classifier["confusion_matrix"],
        "cold_start_latency_ms": first_latency,
        "warm_mean_retrieval_latency_ms": sum(latencies[1:]) / (count - 1),
        "warm_p95_retrieval_latency_ms": sorted(latencies[1:])[int(0.95 * (count - 2))],
        "per_domain_recall_at_1": {
            domain: values["correct"] / values["total"] for domain, values in per_domain.items()
        },
    }
    with open("data/retrieval_eval_results.json", "w") as handle:
        json.dump(results, handle, indent=2)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
