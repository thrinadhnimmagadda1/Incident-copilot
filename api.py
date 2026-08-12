import json
import json as json_module
import time
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from diagnose import diagnose_anomaly, diagnose_anomaly_stream, retrieve_similar_incidents

load_dotenv()

app = FastAPI(
    title="Incident Copilot API",
    description="AI-powered production incident diagnosis using RAG over historical incidents",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request/Response models ───────────────────────────────────
class AnomalyRequest(BaseModel):
    trigger_message: str
    trigger_raw: str = ""


class DiagnosisResponse(BaseModel):
    matched_incident_id: str | None
    matched_incident_title: str | None
    confidence: str
    likely_root_cause: str
    suggested_fix: str
    reasoning: str
    sources: list[dict] = Field(default_factory=list)

class IncidentSummary(BaseModel):
    id: str
    title: str
    system: str
    severity: str


REQUESTS = Counter("incident_copilot_http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("incident_copilot_http_request_seconds", "HTTP request latency", ["path"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    REQUESTS.labels(request.method, request.url.path, response.status_code).inc()
    LATENCY.labels(request.url.path).observe(time.perf_counter() - started)
    return response


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "running", "service": "Incident Copilot API"}

@app.get("/health")
def health():
    with open("data/incidents.json") as f:
        incidents = json.load(f)
    return {
        "status": "healthy",
        "incidents_in_knowledge_base": len(incidents),
    }


@app.post("/diagnose", response_model=DiagnosisResponse)
def diagnose(request: AnomalyRequest):
    """
    Given a log anomaly trigger, retrieve similar past incidents
    and generate a structured diagnosis with confidence level.
    """
    if not request.trigger_message.strip():
        raise HTTPException(status_code=400, detail="trigger_message cannot be empty")

    anomaly = {
        "trigger_message": request.trigger_message,
        "trigger_raw": request.trigger_raw or request.trigger_message,
    }

    try:
        diagnosis = diagnose_anomaly(anomaly)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnosis failed: {str(e)}")

    return DiagnosisResponse(**diagnosis.model_dump())


@app.get("/incidents", response_model=list[IncidentSummary])
def list_incidents():
    """List all incidents in the knowledge base."""
    with open("data/incidents.json") as f:
        incidents = json.load(f)
    return [
        IncidentSummary(
            id=inc["id"],
            title=inc["title"],
            system=inc["system"],
            severity=inc["severity"],
        )
        for inc in incidents
    ]


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    """Get full details for one incident."""
    with open("data/incidents.json") as f:
        incidents = json.load(f)
    for inc in incidents:
        if inc["id"] == incident_id:
            return inc
    raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")


@app.get("/eval-results")
def eval_results():
    """Return the last full-LLM/RAGAS evaluation results."""
    try:
        with open("data/eval_results.json") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No evaluation results found — run evaluate_diagnosis.py first")


@app.get("/retrieval-eval-results")
def retrieval_eval_results():
    """Return the latest offline retrieval benchmark results."""
    try:
        with open("data/retrieval_eval_results.json") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No retrieval benchmark found — run evaluate_retrieval.py first")


@app.get("/similar")
def similar_incidents(query: str, n: int = 3):
    """Debug endpoint — see raw retrieval results for any query."""
    candidates = retrieve_similar_incidents(query, n=n)
    return {"query": query, "candidates": candidates}


@app.post("/diagnose/stream")
def diagnose_stream(request: AnomalyRequest):
    """
    Same as /diagnose but streams progress updates via SSE
    as the system retrieves candidates and generates the diagnosis.
    """
    if not request.trigger_message.strip():
        raise HTTPException(status_code=400, detail="trigger_message cannot be empty")

    anomaly = {
        "trigger_message": request.trigger_message,
        "trigger_raw": request.trigger_raw or request.trigger_message,
    }

    def generate():
        for update in diagnose_anomaly_stream(anomaly):
            yield f"data: {json_module.dumps(update)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
