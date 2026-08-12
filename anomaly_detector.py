"""Consume logs, detect rate spikes, and request an AI diagnosis."""

import json
import logging
import time
from collections import deque
from datetime import datetime, timezone

from kafka import KafkaConsumer

from config import (
    ANOMALY_COOLDOWN_SECONDS,
    ANOMALY_SPIKE_THRESHOLD,
    ANOMALY_WINDOW_SECONDS,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("incident-copilot.detector")


class SlidingWindowDetector:
    """Rate-based detector with a cooldown to suppress duplicate incidents."""

    def __init__(self, window_seconds=5, threshold=5, cooldown_seconds=30):
        self.window_seconds = window_seconds
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.events = deque()
        self.last_detection_at = None

    def observe(self, timestamp):
        while self.events and timestamp - self.events[0] > self.window_seconds:
            self.events.popleft()
        self.events.append(timestamp)

        if len(self.events) < self.threshold:
            return False
        if self.last_detection_at is not None:
            if timestamp - self.last_detection_at < self.cooldown_seconds:
                return False

        self.last_detection_at = timestamp
        self.events.clear()
        return True


def create_consumer():
    return KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset="earliest",
        group_id="incident-copilot-detector",
        enable_auto_commit=True,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )


def run():
    # Imported lazily so unit tests do not initialize the embedding model or LLM.
    from diagnose import diagnose_anomaly

    detector = SlidingWindowDetector(
        ANOMALY_WINDOW_SECONDS,
        ANOMALY_SPIKE_THRESHOLD,
        ANOMALY_COOLDOWN_SECONDS,
    )
    anomalies = []
    logger.info(
        "detector_started topic=%s threshold=%s window_seconds=%s",
        KAFKA_TOPIC,
        ANOMALY_SPIKE_THRESHOLD,
        ANOMALY_WINDOW_SECONDS,
    )

    for message in create_consumer():
        log = message.value
        if log.get("level") not in {"WARN", "WARNING", "ERROR"}:
            continue
        now = time.time()
        if not detector.observe(now):
            continue

        anomaly = {
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "trigger_message": log.get("message", ""),
            "trigger_raw": log.get("raw", ""),
        }
        try:
            anomaly["diagnosis"] = diagnose_anomaly(anomaly).model_dump()
            logger.info(
                "anomaly_diagnosed incident_id=%s confidence=%s",
                anomaly["diagnosis"]["matched_incident_id"],
                anomaly["diagnosis"]["confidence"],
            )
        except Exception:
            logger.exception("diagnosis_failed")
            anomaly["diagnosis"] = {"confidence": "error"}
        anomalies.append(anomaly)

        with open("data/detected_anomalies.json", "w") as handle:
            json.dump(anomalies, handle, indent=2)


if __name__ == "__main__":
    run()
