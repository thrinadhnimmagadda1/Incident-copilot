import json
import time
from collections import deque
from datetime import datetime
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    "service-logs",
    bootstrap_servers="localhost:9092",
    auto_offset_reset="earliest",
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    consumer_timeout_ms=10000
)

WINDOW_SECONDS = 5
SPIKE_THRESHOLD = 5

recent_warnings = deque()

def is_anomaly_window():
    now = time.time()
    while recent_warnings and now - recent_warnings[0] > WINDOW_SECONDS:
        recent_warnings.popleft()
    return len(recent_warnings) >= SPIKE_THRESHOLD

print(f"Anomaly detector running — threshold: {SPIKE_THRESHOLD} warnings/{WINDOW_SECONDS}s\n")

anomalies_detected = []
total = 0
warn_count = 0

for msg in consumer:
    log = msg.value
    total += 1

    if log["level"] in ("WARN", "ERROR"):
        warn_count += 1
        recent_warnings.append(time.time())

        if is_anomaly_window():
            anomaly = {
                "detected_at": datetime.now().isoformat(),
                "trigger_message": log["message"],
                "trigger_raw": log["raw"],
                "warning_count_in_window": len(recent_warnings)
            }
            anomalies_detected.append(anomaly)
            print(f"ANOMALY: {len(recent_warnings)} warnings in {WINDOW_SECONDS}s window")
            print(f"   Trigger: {log['message'][:80]}")
            recent_warnings.clear()

print(f"\n--- Summary ---")
print(f"Total logs processed: {total}")
print(f"Total WARN/ERROR logs: {warn_count}")
print(f"Anomalies detected: {len(anomalies_detected)}")

with open("data/detected_anomalies.json", "w") as f:
    json.dump(anomalies_detected, f, indent=2)
print("Saved to data/detected_anomalies.json")