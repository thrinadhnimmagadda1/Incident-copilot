"""Import JSON/JSONL postmortems or runbooks into the incident catalog."""

import argparse
import json
from pathlib import Path

REQUIRED_FIELDS = {
    "id", "title", "log_pattern", "system", "symptoms", "root_cause",
    "fix", "severity", "resolution_time_minutes",
}


def load_records(path):
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    payload = json.loads(path.read_text())
    return payload if isinstance(payload, list) else [payload]


def validate(record, source):
    missing = REQUIRED_FIELDS - record.keys()
    if missing:
        raise ValueError(f"{source}: missing fields {sorted(missing)}")
    record["source"] = record.get("source", str(source))
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--catalog", type=Path, default=Path("data/incidents.json"))
    args = parser.parse_args()

    catalog = {item["id"]: item for item in json.loads(args.catalog.read_text())}
    for path in args.paths:
        for record in load_records(path):
            validated = validate(record, path)
            catalog[validated["id"]] = validated
    args.catalog.write_text(json.dumps(list(catalog.values()), indent=2) + "\n")
    print(f"Catalog now contains {len(catalog)} incidents. Rebuild the knowledge base next.")


if __name__ == "__main__":
    main()
