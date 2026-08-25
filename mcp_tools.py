"""Local MCP-style tools for incident investigation.

These functions model the tool boundary an MCP server would expose in a real
deployment: log search, metrics lookup, deployment lookup, runbook search, and
ticket drafting. They are deterministic so tests can validate agent behavior.
"""

from collections import Counter
from datetime import datetime, timezone


def get_recent_logs(anomaly, limit=5):
    trigger_log = anomaly.get("trigger_log") or {}
    raw_log = anomaly.get("trigger_raw") or trigger_log.get("raw") or ""
    message = anomaly.get("trigger_message") or trigger_log.get("message") or ""

    logs = []
    if raw_log:
        logs.append(raw_log)
    elif message:
        logs.append(message)

    return {
        "tool": "logs.search_recent",
        "result": logs[:limit],
        "summary": "Found trigger log from the live Kafka event.",
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
        "result": {
            "component": anomaly.get("component") or trigger_log.get("component", "unknown"),
            "status_code": status_code,
            "latency_seconds": latency,
            "risk_signals": risk_signals,
        },
        "summary": ", ".join(risk_signals) if risk_signals else "No metric risk signal found.",
    }


def get_recent_deployments(anomaly):
    component = anomaly.get("component") or (anomaly.get("trigger_log") or {}).get("component", "")
    service = component.split(".")[0] if component else "unknown-service"

    return {
        "tool": "deployments.get_recent",
        "result": [
            {
                "service": service,
                "version": "current-demo-version",
                "deployed_at": "unknown",
                "source": "simulated deployment evidence",
            }
        ],
        "summary": (
            "No real deployment feed is connected yet; agent should ask a human "
            "to verify recent changes before rollback."
        ),
    }


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
