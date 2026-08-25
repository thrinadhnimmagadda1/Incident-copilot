from diagnose import IncidentDiagnosis
from incident_agent import investigate_incident


def test_agent_investigation_collects_evidence_and_ticket(monkeypatch):
    candidate = {
        "id": "INC-005",
        "title": "Nova API elevated response latency during instance list queries",
        "distance": 0.2,
        "source": "data/incidents.json",
    }
    diagnosis = IncidentDiagnosis(
        matched_incident_id="INC-005",
        matched_incident_title=candidate["title"],
        confidence="high",
        likely_root_cause="Nova API query is slow.",
        suggested_fix="Check database index.",
        reasoning="Matched OpenStack latency runbook.",
        sources=[],
    )
    monkeypatch.setattr("incident_agent.retrieve_similar_incidents", lambda _trigger: [candidate])
    monkeypatch.setattr("incident_agent.diagnose_anomaly", lambda _anomaly: diagnosis)

    result = investigate_incident(
        {
            "trigger_message": "GET servers detail slow",
            "trigger_raw": "nova api status: 200 time: 3.5",
            "signal_type": "latency_spike",
            "severity": "medium",
            "component": "nova.osapi_compute.wsgi.server",
            "reason": "latency 3.5s is higher than baseline",
            "trigger_log": {
                "component": "nova.osapi_compute.wsgi.server",
                "status_code": 200,
                "latency_seconds": 3.5,
            },
        }
    )

    assert result.status == "investigated"
    assert result.human_approval_required is True
    assert result.ticket["requires_human_approval"] is True
    assert len(result.evidence) == 5
    assert result.diagnosis["matched_incident_id"] == "INC-005"


def test_agent_adds_human_guidance_when_no_runbook_match(monkeypatch):
    diagnosis = IncidentDiagnosis(
        matched_incident_id=None,
        matched_incident_title=None,
        confidence="no_match",
        likely_root_cause="No similar historical incident found in knowledge base",
        suggested_fix="Escalate to human on-call engineer",
        reasoning="No close vector match.",
        sources=[],
    )
    monkeypatch.setattr("incident_agent.retrieve_similar_incidents", lambda _trigger: [])
    monkeypatch.setattr("incident_agent.diagnose_anomaly", lambda _anomaly: diagnosis)

    result = investigate_incident(
        {
            "trigger_message": "connection refused from scheduler",
            "trigger_raw": "nova api connection refused",
            "signal_type": "unknown_risk_pattern",
            "severity": "medium",
            "component": "nova.api",
            "reason": "log contains a risky failure phrase",
            "trigger_log": {
                "component": "nova.api",
                "message": "backend connection refused while contacting scheduler",
            },
        }
    )

    assert result.diagnosis["confidence"] == "no_match"
    assert "No exact runbook match" in result.diagnosis["likely_root_cause"]
    assert "Do not auto-rollback" in result.diagnosis["suggested_fix"]
    assert result.ticket["requires_human_approval"] is True
