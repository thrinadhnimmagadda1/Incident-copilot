"""
Test script: feed the diagnosis system a completely unrelated
anomaly to verify it honestly reports low confidence / no match
instead of forcing a false match.
"""
from diagnose import diagnose_anomaly

# A fake anomaly totally unrelated to any of our 6 incidents
fake_anomaly = {
    "trigger_message": "Payment gateway returned HTTP 503 for checkout requests, credit card processor timeout after 30s",
    "trigger_raw": "2026-07-25 ERROR payments.gateway: HTTP 503 checkout timeout processor_id=stripe_prod_3"
}

print("Testing with an UNRELATED anomaly (should NOT match well)...\n")
print(f"Trigger: {fake_anomaly['trigger_message']}\n")

diagnosis = diagnose_anomaly(fake_anomaly)

print(f"Matched: {diagnosis.matched_incident_id}")
print(f"Confidence: {diagnosis.confidence}")
print(f"Root cause: {diagnosis.likely_root_cause}")
print(f"Reasoning: {diagnosis.reasoning}")

print("\n" + "="*60)
if diagnosis.confidence in ("no_match", "low"):
    print("PASS: System honestly reported low/no match for unrelated anomaly")
else:
    print("WARNING: System forced a match for something unrelated!")
    print("This means the guardrail/prompt needs strengthening.")