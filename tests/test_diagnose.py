from types import SimpleNamespace

import diagnose


class FakeModel:
    def encode(self, _texts):
        return SimpleNamespace(tolist=lambda: [[0.1, 0.2]])


class FakeCollection:
    def query(self, **_kwargs):
        return {
            "ids": [["INC-001"]],
            "metadatas": [[{
                "id": "INC-001",
                "title": "DataNode exception",
                "root_cause": "network saturation",
                "fix": "throttle replication",
                "severity": "medium",
                "source": "runbooks/hdfs.md",
            }]],
            "distances": [[0.25]],
        }


def test_retrieval_maps_vector_results(monkeypatch):
    monkeypatch.setattr(diagnose, "get_retrieval_resources", lambda: (FakeCollection(), FakeModel()))
    matches = diagnose.retrieve_similar_incidents("DataNode failed")
    assert matches[0]["id"] == "INC-001"
    assert matches[0]["source"] == "runbooks/hdfs.md"


def test_distance_guardrail_refuses_novel_incident(monkeypatch):
    monkeypatch.setattr(diagnose, "retrieve_similar_incidents", lambda _query: [{"distance": 9.0}])
    result = diagnose.diagnose_anomaly({"trigger_message": "novel error", "trigger_raw": "novel error"})
    assert result.confidence == "no_match"
    assert result.matched_incident_id is None


def test_malformed_llm_output_fails_safe(monkeypatch):
    candidate = {
        "id": "INC-001", "title": "Known", "root_cause": "cause", "fix": "fix",
        "severity": "medium", "distance": 0.1, "source": "data/incidents.json",
    }
    monkeypatch.setattr(diagnose, "retrieve_similar_incidents", lambda _query: [candidate])
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="not-json"))]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_kwargs: response))
    )
    monkeypatch.setattr(diagnose, "get_llm_client", lambda: client)
    result = diagnose.diagnose_anomaly({"trigger_message": "known", "trigger_raw": "known"})
    assert result.confidence == "no_match"
    assert result.likely_root_cause == "Failed to parse diagnosis"
