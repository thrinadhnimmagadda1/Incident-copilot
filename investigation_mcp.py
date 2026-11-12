"""Real stdio MCP transport. Only the bundled read-only tools are callable."""

import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TOOLS = {
    "search_recent_logs": "Search recent service logs.",
    "get_service_health": "Inspect observed latency and status signals.",
    "get_recent_deployment_evidence": "Read GitHub deployment history if configured.",
    "search_incident_runbooks": "Inspect historical incident candidates.",
}


@asynccontextmanager
async def connect_tools():
    root = Path(__file__).resolve().parent
    # The evidence server does not need access to model-provider credentials.
    env = {k: v for k, v in os.environ.items() if k in {
        "PATH", "SYSTEMROOT", "HOME", "LOG_SOURCE", "LOG_FILE_PATH",
        "GITHUB_TOKEN", "GITHUB_REPOSITORY",
    }}
    params = StdioServerParameters(
        command=sys.executable, args=[str(root / "mcp_server.py")], cwd=str(root), env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=15)) as session:
            await session.initialize()
            available = {tool.name for tool in (await session.list_tools()).tools}
            if not set(TOOLS).issubset(available):
                raise RuntimeError("Investigation MCP server is missing required tools")

            async def call(name, arguments):
                if name not in TOOLS:
                    raise ValueError("Tool is not allowed")
                result = await session.call_tool(name, arguments)
                if result.isError:
                    raise RuntimeError(f"MCP tool failed: {name}")
                payload = result.structuredContent
                if payload is None:
                    payload = json.loads(next(c.text for c in result.content if c.type == "text"))
                if not isinstance(payload, dict) or "tool" not in payload:
                    raise ValueError("Invalid MCP evidence")
                return payload

            yield call
