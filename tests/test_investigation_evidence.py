from types import SimpleNamespace

import diagnose
import mcp_tools


def test_github_deployments_reads_real_api_with_timeout(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/service")
    def get(url, **kwargs):
        assert url == "https://api.github.com/repos/example/service/deployments"
        assert kwargs["timeout"] == 8
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: [{
            "sha": "abc", "environment": "staging", "created_at": "2026-11-11T10:00:00Z",
            "url": "https://api.github.com/repos/example/service/deployments/1",
        }])
    monkeypatch.setattr(mcp_tools.requests, "get", get)
    assert mcp_tools.get_recent_deployments({})["result"][0]["sha"] == "abc"


def test_local_log_history_is_filtered_to_component(tmp_path, monkeypatch):
    path = tmp_path / "events.log"
    path.write_text("081109 203615 148 WARN dfs.DataNode: failed\n"
                    "081109 203615 148 INFO other.Service: healthy\n")
    monkeypatch.setattr(mcp_tools, "LOG_FILE_PATH", str(path))
    monkeypatch.setattr(mcp_tools, "LOG_SOURCE", "HDFS")
    result = mcp_tools.get_recent_logs({"component": "dfs.DataNode"})
    assert len(result["result"]) == 1
    assert result["result"][0]["component"] == "dfs.DataNode"


def test_diagnosis_receives_evidence_and_rejects_invented_incident(monkeypatch):
    def create(**kwargs):
        assert "deployment-observation-123" in kwargs["messages"][0]["content"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='''{
            "matched_incident_id":"FAKE", "matched_incident_title":"Invented",
            "confidence":"high", "likely_root_cause":"cause", "suggested_fix":"fix",
            "reasoning":"reason", "sources":[]
        }'''))])
    monkeypatch.setattr(diagnose, "get_llm_client", lambda: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    result = diagnose.diagnose_anomaly(
        {"trigger_message": "failed", "trigger_raw": "failed"},
        candidates=[{"id": "INC-001", "title": "Known", "root_cause": "cause",
                     "fix": "fix", "severity": "low", "distance": 0.1}],
        evidence=[{"tool": "deployments.get_recent", "result": "deployment-observation-123"}],
    )
    assert result.confidence == "no_match"
    assert result.sources == []
