from fastapi.testclient import TestClient

import api

client = TestClient(api.app)


def test_root_and_request_id():
    response = client.get("/", headers={"X-Request-ID": "test-request"})
    assert response.status_code == 200
    assert response.json()["service"] == "Incident Copilot API"
    assert response.headers["X-Request-ID"] == "test-request"


def test_diagnose_rejects_empty_message():
    response = client.post("/diagnose", json={"trigger_message": "   "})
    assert response.status_code == 400


def test_incident_not_found():
    response = client.get("/incidents/DOES-NOT-EXIST")
    assert response.status_code == 404
