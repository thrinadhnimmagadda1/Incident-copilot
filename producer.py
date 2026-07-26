import json
import time
import re
from datetime import datetime
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
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

def stream_logs(filepath, topic="service-logs", delay=0.05):
    sent = 0
    with open(filepath) as f:
        for line in f:
            parsed = parse_hdfs_line(line)
            if parsed:
                producer.send(topic, parsed)
                sent += 1
                if parsed["level"] in ("WARN", "ERROR"):
                    print(f"  -> [{parsed['level']}] {parsed['message'][:70]}")
                time.sleep(delay)
    producer.flush()
    print(f"\nStreamed {sent} log lines to topic '{topic}'")

if __name__ == "__main__":
    print("Streaming HDFS logs to Kafka...")
    stream_logs("data/HDFS_2k.log")