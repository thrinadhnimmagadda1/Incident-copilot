import os
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dotenv import load_dotenv

from diagnose import diagnose_anomaly, retrieve_similar_incidents, diagnose_anomaly_stream
import json as json_module
from fastapi.responses import StreamingResponse

load_dotenv()

app = FastAPI(
    title="Incident Copilot API",
    description="AI-powered production incident diagnosis using RAG over historical incidents",
    version="1.0.0"
)
from fastapi.middleware.cors import CORSMiddleware

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

class IncidentSummary(BaseModel):
    id: str
    title: str
    system: str
    severity: str

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
        "incidents_in_knowledge_base": len(incidents)
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
        "trigger_raw": request.trigger_raw or request.trigger_message
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
            severity=inc["severity"]
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
    """Return the last RAGAS evaluation results."""
    try:
        with open("data/eval_results.json") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No evaluation results found — run evaluate_diagnosis.py first")

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
        "trigger_raw": request.trigger_raw or request.trigger_message
    }

    def generate():
        for update in diagnose_anomaly_stream(anomaly):
            yield f"data: {json_module.dumps(update)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")