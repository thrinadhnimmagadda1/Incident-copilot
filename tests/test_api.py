import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402

client = TestClient(api.app)


def test_root_and_request_id():
    response = client.get("/", headers={"X-Request-ID": "test-request"})
    assert response.status_code == 200
    assert response.json()["service"] == "Incident Copilot API"
    assert response.headers["X-Request-ID"] == "test-request"


def test_diagnose_rejects_empty_message():
    response = client.post("/diagnose", json={"trigger_message": "   "})
    assert response.status_code == 400


def test_agent_investigate_endpoint(monkeypatch):
    class FakeInvestigation:
        def model_dump(self):
            return {
                "status": "investigated",
                "agent_steps": ["Read anomaly from Kafka detector."],
                "evidence": [],
                "diagnosis": {
                    "matched_incident_id": None,
                    "matched_incident_title": None,
                    "confidence": "no_match",
                    "likely_root_cause": "No exact runbook match.",
                    "suggested_fix": "Human review required.",
                    "reasoning": "Evidence was weak.",
                    "sources": [],
                },
                "ticket": {
                    "title": "MEDIUM incident in manual.input",
                    "confidence": "no_match",
                    "suggested_fix": "Human review required.",
                    "requires_human_approval": True,
                },
                "human_approval_required": True,
            }

    monkeypatch.setattr(api, "investigate_incident", lambda _anomaly: FakeInvestigation())

    response = client.post("/agent/investigate", json={"trigger_message": "connection refused"})

    assert response.status_code == 200
    assert response.json()["human_approval_required"] is True
    assert response.json()["ticket"]["requires_human_approval"] is True


def test_incident_not_found():
    response = client.get("/incidents/DOES-NOT-EXIST")
    assert response.status_code == 404
