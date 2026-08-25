"""Consume logs, detect suspicious operational signals, and request an AI diagnosis."""

import json
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

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


class OperationalSignalDetector:
    """Detect errors, latency spikes, and unknown risky log patterns per service."""

    def __init__(
        self,
        window_seconds=5,
        error_threshold=5,
        latency_threshold_seconds=1.0,
        latency_ratio=2.0,
        cooldown_seconds=30,
    ):
        self.window_seconds = window_seconds
        self.error_threshold = error_threshold
        self.latency_threshold_seconds = latency_threshold_seconds
        self.latency_ratio = latency_ratio
        self.cooldown_seconds = cooldown_seconds
        self.events_by_component = defaultdict(deque)
        self.latency_baseline_by_component = defaultdict(deque)
        self.last_detection_by_signal = {}

    def observe(self, log, timestamp):
        component = log.get("component") or "unknown"
        events = self.events_by_component[component]
        self._expire(events, timestamp)
        events.append((timestamp, log))

        signals = []
        if self._is_error(log):
            error_count = sum(1 for _, event in events if self._is_error(event))
            if error_count >= self.error_threshold:
                signals.append(
                    {
                        "type": "error_burst",
                        "severity": "high",
                        "reason": f"{error_count} error-like events inside {self.window_seconds}s",
                    }
                )

        latency_signal = self._latency_signal(log, component)
        if latency_signal:
            signals.append(latency_signal)

        unknown_signal = self._unknown_risk_signal(log)
        if unknown_signal:
            signals.append(unknown_signal)

        for signal in signals:
            signal_key = (component, signal["type"])
            if self._cooling_down(signal_key, timestamp):
                continue
            self.last_detection_by_signal[signal_key] = timestamp
            return {
                "signal_type": signal["type"],
                "severity": signal["severity"],
                "component": component,
                "reason": signal["reason"],
                "observed_window_seconds": self.window_seconds,
            }
        return None

    def _expire(self, events, timestamp):
        while events and timestamp - events[0][0] > self.window_seconds:
            events.popleft()

    def _cooling_down(self, signal_key, timestamp):
        last_detection_at = self.last_detection_by_signal.get(signal_key)
        return (
            last_detection_at is not None
            and timestamp - last_detection_at < self.cooldown_seconds
        )

    def _is_error(self, log):
        level = log.get("level")
        status_code = log.get("status_code") or 0
        message = (log.get("message") or "").lower()
        return (
            level in {"WARN", "WARNING", "ERROR", "CRITICAL"}
            or status_code >= 500
            or "exception" in message
            or "failed" in message
            or "timeout" in message
        )

    def _latency_signal(self, log, component):
        latency = log.get("latency_seconds")
        if latency is None:
            return None

        baseline = self.latency_baseline_by_component[component]
        historical_average = sum(baseline) / len(baseline) if baseline else latency
        baseline.append(latency)
        if len(baseline) > 50:
            baseline.popleft()

        if latency < self.latency_threshold_seconds:
            return None
        if latency < historical_average * self.latency_ratio:
            return None

        return {
            "type": "latency_spike",
            "severity": "medium",
            "reason": (
                f"latency {latency:.3f}s is much higher than recent average "
                f"{historical_average:.3f}s"
            ),
        }

    def _unknown_risk_signal(self, log):
        message = (log.get("message") or "").lower()
        risky_words = ("traceback", "connection refused", "unavailable", "reset by peer")
        if any(word in message for word in risky_words):
            return {
                "type": "unknown_risk_pattern",
                "severity": "medium",
                "reason": "log contains a risky failure phrase that may not be in the runbook",
            }
        return None


def create_consumer():
    from kafka import KafkaConsumer

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
    from incident_agent import investigate_incident

    detector = OperationalSignalDetector(
        ANOMALY_WINDOW_SECONDS,
        ANOMALY_SPIKE_THRESHOLD,
        cooldown_seconds=ANOMALY_COOLDOWN_SECONDS,
    )
    legacy_detector = SlidingWindowDetector(
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
        now = time.time()
        signal = detector.observe(log, now)
        if not signal and log.get("level") in {"WARN", "WARNING", "ERROR"}:
            if legacy_detector.observe(now):
                signal = {
                    "signal_type": "warning_error_rate_spike",
                    "severity": "medium",
                    "component": log.get("component", "unknown"),
                    "reason": "WARN/ERROR rate exceeded legacy sliding-window threshold",
                    "observed_window_seconds": ANOMALY_WINDOW_SECONDS,
                }
        if not signal:
            continue

        anomaly = {
            "detected_at": datetime.now(timezone.utc).isoformat(),
            **signal,
            "trigger_message": log.get("message", ""),
            "trigger_raw": log.get("raw", ""),
            "trigger_log": log,
        }
        try:
            investigation = investigate_incident(anomaly).model_dump()
            anomaly["agent_investigation"] = investigation
            anomaly["diagnosis"] = investigation["diagnosis"]
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
