import asyncio
from contextlib import asynccontextmanager

import pytest

from diagnose import IncidentDiagnosis
from incident_agent import investigate_async
from investigation_mcp import connect_tools


@asynccontextmanager
async def fake_tools():
    async def call(name, arguments):
        return {"tool": name, "result": arguments, "summary": "test evidence"}
    yield call


def diagnosis(anomaly, *, candidates, evidence):
    assert evidence[0]["tool"] == "search_recent_logs"
    return IncidentDiagnosis(
        matched_incident_id="INC-001", matched_incident_title="Test", confidence="high",
        likely_root_cause="Observed failure", suggested_fix="Review runbook",
        reasoning="Evidence supplied", sources=[],
    )


def run(planner, connector=fake_tools, diagnosis_fn=diagnosis):
    return asyncio.run(investigate_async(
        {"trigger_message": "error", "trigger_raw": "error"},
        connector=connector, planner=planner,
        retrieval=lambda _: [], diagnosis_fn=diagnosis_fn,
    ))


def test_evidence_reaches_diagnosis_and_human_review():
    result = run(lambda *_: "finish")
    assert result.status == "awaiting_human_review"
    assert result.human_approval_required
    assert result.ticket["requires_human_approval"]


@pytest.mark.parametrize("name", ["delete_pods", "search_recent_logs", "invalid JSON"])
def test_disallowed_or_repeated_tool_stops_investigation(name):
    result = run(lambda *_: name)
    assert result.status == "needs_human_investigation"
    assert result.diagnosis["confidence"] == "no_match"
    assert len(result.evidence) == 1


def test_tool_timeout_preserves_evidence_and_stops():
    @asynccontextmanager
    async def broken_tools():
        async def call(*_):
            raise TimeoutError("secret-provider-data")
        yield call
    result = run(lambda *_: "finish", connector=broken_tools)
    assert result.status == "needs_human_investigation"
    assert "secret-provider-data" not in result.model_dump_json()


def test_tool_budget_is_four():
    result = run(lambda _a, _e, remaining: next(iter(remaining)))
    assert len(result.evidence) == 4


def test_real_mcp_subprocess_handshake_and_tool_call():
    async def check():
        async with connect_tools() as call:
            result = await call("search_recent_logs", {"anomaly": {"trigger_message": "sample"}})
            assert result["result"] == ["sample"]
            with pytest.raises(ValueError):
                await call("delete_pods", {})
    asyncio.run(check())
