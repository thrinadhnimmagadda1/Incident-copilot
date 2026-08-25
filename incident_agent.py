"""Agentic investigation layer for detected incidents."""

from pydantic import BaseModel, Field

from diagnose import IncidentDiagnosis, diagnose_anomaly, retrieve_similar_incidents
from mcp_tools import collect_investigation_evidence, draft_ticket


class AgentInvestigation(BaseModel):
    status: str
    agent_steps: list[str] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    diagnosis: dict
    ticket: dict
    human_approval_required: bool = True


def investigate_incident(anomaly):
    """Investigate an anomaly by using MCP-style tools before making a recommendation."""
    trigger = anomaly["trigger_message"]
    steps = [
        "Read anomaly from Kafka detector.",
        "Search recent logs for the triggering event.",
        "Check service health signals such as status code and latency.",
        "Check recent deployment evidence.",
        "Search runbooks and past incidents.",
        "Generate diagnosis and human-safe recommendation.",
    ]

    candidates = retrieve_similar_incidents(trigger)
    evidence = collect_investigation_evidence(anomaly, candidates)
    diagnosis = diagnose_anomaly(anomaly)

    if diagnosis.confidence == "no_match":
        diagnosis = add_uncertain_agent_guidance(anomaly, diagnosis)

    ticket = draft_ticket(anomaly, diagnosis, evidence)
    evidence.append(ticket)

    return AgentInvestigation(
        status="investigated",
        agent_steps=steps,
        evidence=evidence,
        diagnosis=diagnosis.model_dump(),
        ticket=ticket["result"],
        human_approval_required=True,
    )


def add_uncertain_agent_guidance(anomaly, diagnosis):
    signal_type = anomaly.get("signal_type", "unknown signal").replace("_", " ")
    component = anomaly.get("component", "unknown component")
    reason = anomaly.get("reason", "the live signal looked risky")

    return IncidentDiagnosis(
        matched_incident_id=None,
        matched_incident_title=None,
        confidence="no_match",
        likely_root_cause=(
            f"No exact runbook match was found. The issue may be in {component}; "
            f"the live detector saw {signal_type}: {reason}."
        ),
        suggested_fix=(
            "Ask the human on-call engineer to inspect this component first, verify "
            "recent deployment/config changes, and consider rollback only if the "
            "timeline supports it. Do not auto-rollback."
        ),
        reasoning=(
            "The agent used MCP-style tools for logs, metrics, deployments, and "
            "runbooks, but evidence was not strong enough for an automatic fix."
        ),
        sources=diagnosis.sources,
    )
