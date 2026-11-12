"""MCP server exposing incident-investigation tools."""

from mcp.server.fastmcp import FastMCP

from mcp_tools import (
    get_recent_deployments,
    get_recent_logs,
    get_service_metrics,
    search_runbooks,
)

mcp = FastMCP("incident-copilot")


@mcp.tool()
def search_recent_logs(anomaly: dict, limit: int = 5) -> dict:
    """Return recent log evidence for a detected anomaly."""
    return get_recent_logs(anomaly, limit)


@mcp.tool()
def get_service_health(anomaly: dict) -> dict:
    """Return service health signals such as status code, latency, and risk type."""
    return get_service_metrics(anomaly)


@mcp.tool()
def get_recent_deployment_evidence(anomaly: dict) -> dict:
    """Return recent deployment evidence for the affected service."""
    return get_recent_deployments(anomaly)


@mcp.tool()
def search_incident_runbooks(anomaly: dict, candidates: list[dict]) -> dict:
    """Return historical runbook candidates already retrieved for the anomaly."""
    return search_runbooks(anomaly, candidates)


if __name__ == "__main__":
    mcp.run()
