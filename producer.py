import json
import re
import time
from datetime import datetime

from config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC, LOG_FILE_PATH, LOG_SOURCE


def create_producer():
    from kafka import KafkaProducer

    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        retries=5,
    )

def parse_hdfs_line(line):
    match = re.match(r"(\d{6}) (\d{6}) (\d+) (\w+) ([\w$.]+): (.+)", line)
    if not match:
        return None
    date, time_, pid, level, component, message = match.groups()
    return {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "component": component,
        "message": message,
        "raw": line.strip()
    }


def parse_openstack_line(line):
    match = re.match(
        r"(\S+) "
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) "
        r"(\d+) "
        r"(\w+) "
        r"([\w$.]+) "
        r"(.+)",
        line,
    )
    if not match:
        return None

    filename, source_timestamp, pid, level, component, message = match.groups()
    request_id_match = re.search(r"\[(req-[^\s\]]+)", message)
    status_match = re.search(r"status:\s*(\d+)", message)
    latency_match = re.search(r"time:\s*([0-9.]+)", message)

    return {
        "timestamp": datetime.now().isoformat(),
        "source_timestamp": source_timestamp,
        "level": level,
        "component": component,
        "message": message,
        "raw": line.strip(),
        "source": "OpenStack",
        "filename": filename,
        "pid": pid,
        "request_id": request_id_match.group(1) if request_id_match else None,
        "status_code": int(status_match.group(1)) if status_match else None,
        "latency_seconds": float(latency_match.group(1)) if latency_match else None,
    }


def parse_log_line(line, source=LOG_SOURCE):
    if source.lower() == "openstack":
        return parse_openstack_line(line)
    if source.lower() == "hdfs":
        return parse_hdfs_line(line)
    raise ValueError(f"Unsupported LOG_SOURCE '{source}'. Use OpenStack or HDFS.")


def stream_logs(filepath=LOG_FILE_PATH, topic=KAFKA_TOPIC, delay=0.05, source=LOG_SOURCE):
    producer = create_producer()
    sent = 0
    with open(filepath) as f:
        for line in f:
            parsed = parse_log_line(line, source)
            if parsed:
                producer.send(topic, parsed)
                sent += 1
                status_code = parsed.get("status_code") or 0
                if parsed["level"] in ("WARN", "WARNING", "ERROR") or status_code >= 500:
                    print(f"  -> [{parsed['level']}] {parsed['message'][:70]}")
                time.sleep(delay)
    producer.flush()
    print(f"\nStreamed {sent} {source} log lines from {filepath} to topic '{topic}'")

if __name__ == "__main__":
    print(f"Streaming {LOG_SOURCE} logs to Kafka...")
    stream_logs()
