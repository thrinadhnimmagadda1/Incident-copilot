"""
Build a RAGAS evaluation set for the incident diagnosis system.

Test cases cover:
  1. True positives — anomalies that SHOULD match a known incident
  2. True negatives — anomalies that should NOT match anything
     (tests whether the guardrail holds up under evaluation too)
"""
import json

test_cases = [
    # ── True positives — should match INC-001 (HDFS DataXceiver) ──
    {
        "trigger": "10.251.30.85:50010:Got exception while serving blk_-2918118818249673980 to /10.251.90.64:",
        "expected_incident": "INC-001",
        "expected_confidence_min": "medium",  # should be at least medium
        "ground_truth": "This matches INC-001 - DataNode packet serving exception caused by network instability or peer overload during block replication. Fix: throttle replication bandwidth."
    },
    {
        "trigger": "10.251.126.255:50010:Got exception while serving blk_8376667364205250596 to /10.251.91.159:",
        "expected_incident": "INC-001",
        "expected_confidence_min": "medium",
        "ground_truth": "This matches INC-001 - DataNode packet serving exception caused by network instability or peer overload during block replication. Fix: throttle replication bandwidth."
    },

    # ── True positive — should match INC-005 (OpenStack latency) ──
    {
        "trigger": "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1 status: 200 time: 7.821",
        "expected_incident": "INC-005",
        "expected_confidence_min": "low",  # harder match, less exact wording
        "ground_truth": "This matches INC-005 - Nova API elevated latency caused by unindexed join across instances and instance_metadata tables. Fix: add composite index on project_id and deleted."
    },

    # ── True negatives — should NOT match anything ──────────────
    {
        "trigger": "Payment gateway returned HTTP 503 for checkout requests, credit card processor timeout after 30s",
        "expected_incident": None,
        "expected_confidence_min": "no_match",
        "ground_truth": "No matching incident exists in the knowledge base. This is an unrelated payment system issue, not an HDFS/OpenStack/Spark/Linux infrastructure problem. Should escalate to human."
    },
    {
        "trigger": "React frontend build failed: Module not found, Cannot resolve './components/Header'",
        "expected_incident": None,
        "expected_confidence_min": "no_match",
        "ground_truth": "No matching incident exists in the knowledge base. This is a frontend build error, completely unrelated to any backend infrastructure incident on record."
    },
]

with open("data/eval_set.json", "w") as f:
    json.dump(test_cases, f, indent=2)

print(f"Built evaluation set with {len(test_cases)} test cases")
print(f"  True positives: {sum(1 for t in test_cases if t['expected_incident'])}")
print(f"  True negatives: {sum(1 for t in test_cases if not t['expected_incident'])}")