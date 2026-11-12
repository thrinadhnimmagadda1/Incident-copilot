"""Local MCP-style tools for incident investigation.

These functions model the tool boundary an MCP server would expose in a real
deployment: log search, metrics lookup, deployment lookup, runbook search, and
ticket drafting. They are deterministic so tests can validate agent behavior.
"""

import os
import re
from collections import Counter, deque
from datetime import datetime, timezone

import requests

from config import LOG_FILE_PATH, LOG_SOURCE


def get_recent_logs(anomaly, limit=5):
    trigger_log = anomaly.get("trigger_log") or {}
    raw_log = anomaly.get("trigger_raw") or trigger_log.get("raw") or ""
    message = anomaly.get("trigger_message") or trigger_log.get("message") or ""

    logs = []
    component = anomaly.get("component")
    if component and component != "manual.input":
        from producer import parse_log_line

        try:
            with open(LOG_FILE_PATH) as handle:
                for line in deque(handle, maxlen=1000):
                    parsed = parse_log_line(line, LOG_SOURCE)
                    if parsed and parsed.get("component") == component:
                        logs.append(parsed)
        except FileNotFoundError:
            pass
    if raw_log:
        logs.append(raw_log)
    elif message:
        logs.append(message)

    return {
        "tool": "logs.search_recent",
        "result": logs[-max(1, min(limit, 20)):],
        "summary": "Observed log records; historical replay timestamps are not live production time.",
    }


def get_service_metrics(anomaly):
    trigger_log = anomaly.get("trigger_log") or {}
    status_code = trigger_log.get("status_code")
    latency = trigger_log.get("latency_seconds")
    signal_type = anomaly.get("signal_type")

    risk_signals = []
    if status_code and status_code >= 500:
        risk_signals.append("5xx response")
    if latency and latency >= 1.0:
        risk_signals.append("high latency")
    if signal_type:
        risk_signals.append(signal_type.replace("_", " "))

    return {
        "tool": "metrics.get_service_health",
        "source": "trigger event; no independent metrics backend connected",
        "result": {
            "component": anomaly.get("component") or trigger_log.get("component", "unknown"),
            "status_code": status_code,
            "latency_seconds": latency,
            "risk_signals": risk_signals,
        },
        "summary": ", ".join(risk_signals) if risk_signals else "No metric risk signal found.",
    }


def get_recent_deployments(anomaly):
    repository = os.getenv("GITHUB_REPOSITORY", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        return {"tool": "deployments.get_recent", "result": [], "available": False,
                "summary": "GITHUB_REPOSITORY not configured; deployment history unknown."}
    headers = {"Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    response = requests.get(
        f"https://api.github.com/repos/{repository}/deployments",
        params={"per_page": 5}, headers=headers, timeout=8,
    )
    response.raise_for_status()
    return {"tool": "deployments.get_recent", "available": True,
            "source": f"GitHub deployments: {repository}",
            "result": [{"sha": d["sha"], "environment": d["environment"],
                        "created_at": d["created_at"], "url": d["url"]}
                       for d in response.json()],
            "summary": "Repository history; service correlation must be verified."}


def search_runbooks(anomaly, candidates):
    matched = [
        {
            "incident_id": candidate.get("id"),
            "title": candidate.get("title"),
            "distance": candidate.get("distance"),
            "source": candidate.get("source"),
        }
        for candidate in candidates
    ]
    return {
        "tool": "runbooks.search",
        "result": matched,
        "summary": f"Found {len(matched)} possible historical runbook matches.",
    }


def draft_ticket(anomaly, diagnosis, evidence):
    evidence_counts = Counter(item["tool"] for item in evidence)
    return {
        "tool": "tickets.draft_incident",
        "result": {
            "title": f"{anomaly.get('severity', 'medium').upper()} incident in {anomaly.get('component', 'unknown')}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "confidence": diagnosis.confidence,
            "likely_root_cause": diagnosis.likely_root_cause,
            "suggested_fix": diagnosis.suggested_fix,
            "evidence_tools": dict(evidence_counts),
            "requires_human_approval": True,
        },
        "summary": "Drafted ticket; no production action taken without human approval.",
    }


def collect_investigation_evidence(anomaly, candidates):
    return [
        get_recent_logs(anomaly),
        get_service_metrics(anomaly),
        get_recent_deployments(anomaly),
        search_runbooks(anomaly, candidates),
    ]
