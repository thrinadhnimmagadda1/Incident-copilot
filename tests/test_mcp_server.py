import pytest

pytest.importorskip("mcp")

from mcp_server import (  # noqa: E402
    get_recent_deployment_evidence,
    get_service_health,
    search_incident_runbooks,
    search_recent_logs,
)


def test_mcp_tool_functions_return_expected_evidence():
    anomaly = {
        "component": "nova.api",
        "trigger_raw": "nova api status: 500 time: 1.5",
        "trigger_log": {
            "component": "nova.api",
            "status_code": 500,
            "latency_seconds": 1.5,
        },
        "signal_type": "latency_spike",
    }

    assert search_recent_logs(anomaly)["tool"] == "logs.search_recent"
    assert get_service_health(anomaly)["result"]["status_code"] == 500
    assert get_recent_deployment_evidence(anomaly)["result"][0]["service"] == "nova"
    assert search_incident_runbooks(anomaly, [])["result"] == []
