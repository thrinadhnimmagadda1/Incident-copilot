import json
import os
from typing import Optional

import chromadb
from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from config import (
    CHROMA_PATH,
    DISTANCE_THRESHOLD,
    GROQ_MODEL,
    LLM_MAX_RETRIES,
    LLM_TIMEOUT_SECONDS,
    RETRIEVAL_TOP_K,
)

load_dotenv()

# Heavy resources are initialized lazily so API startup and unit tests stay fast.
groq_client = None
collection = None
embedding_model = None


def get_groq_client():
    global groq_client
    if groq_client is None:
        groq_client = Groq(
            api_key=os.getenv("GROQ_API_KEY"),
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=LLM_MAX_RETRIES,
        )
    return groq_client


def get_retrieval_resources():
    global collection, embedding_model
    if collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_or_create_collection("incident_history")
    if embedding_model is None:
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return collection, embedding_model


# Structured output schema — this is what every diagnosis returns
class IncidentDiagnosis(BaseModel):
    matched_incident_id: Optional[str]
    matched_incident_title: Optional[str]
    confidence: str  # "high", "medium", "low", "no_match"
    likely_root_cause: str
    suggested_fix: str
    reasoning: str
    sources: list[dict] = Field(default_factory=list)


# ── Step 1: Retrieve similar past incidents ───────────────────
def retrieve_similar_incidents(trigger_message: str, n: int = RETRIEVAL_TOP_K):
    incident_collection, model = get_retrieval_resources()
    query_embedding = model.encode([trigger_message]).tolist()
    results = incident_collection.query(
        query_embeddings=query_embedding, n_results=n
    )

    matches = []
    for i in range(len(results["ids"][0])):
        matches.append(
            {
                "id": results["metadatas"][0][i]["id"],
                "title": results["metadatas"][0][i]["title"],
                "root_cause": results["metadatas"][0][i]["root_cause"],
                "fix": results["metadatas"][0][i]["fix"],
                "severity": results["metadatas"][0][i]["severity"],
                "distance": results["distances"][0][i],  # lower = more similar
                "source": results["metadatas"][0][i].get("source", "data/incidents.json"),
            }
        )
    return matches


# ── Step 2: Agent correlates and diagnoses ────────────────────
def diagnose_anomaly(anomaly: dict) -> IncidentDiagnosis:
    trigger = anomaly["trigger_message"]
    raw_log = anomaly["trigger_raw"]

    # Retrieve candidates
    candidates = retrieve_similar_incidents(trigger)

    # GUARDRAIL: hard cutoff BEFORE the LLM ever sees candidates.
    # This prevents the LLM from rationalizing a bad match just
    # because it's "the closest of what's available"
    best_distance = candidates[0]["distance"] if candidates else 999
    if best_distance > DISTANCE_THRESHOLD:
        return IncidentDiagnosis(
            matched_incident_id=None,
            matched_incident_title=None,
            confidence="no_match",
            likely_root_cause="No similar historical incident found in knowledge base",
            suggested_fix="Escalate to human on-call engineer — novel issue not covered by existing runbooks",
            reasoning=f"Best candidate distance ({best_distance:.3f}) exceeds threshold ({DISTANCE_THRESHOLD}). Refusing to force a match to avoid misdiagnosis.",
            sources=[],
        )

    # Build context for the LLM
    candidates_text = ""
    for c in candidates:
        candidates_text += f"""
Incident {c['id']}: {c['title']}
  Root cause: {c['root_cause']}
  Fix applied: {c['fix']}
  Severity: {c['severity']}
  Similarity distance: {c['distance']:.3f} (lower = more similar)
"""

    prompt = f"""You are an on-call incident diagnosis assistant.

A new anomaly was detected in production logs:
Raw log line: {raw_log}
Trigger message: {trigger}

Here are the most similar PAST incidents from the knowledge base:
{candidates_text}

Your task:
1. Decide if the new anomaly TRULY matches one of these past incidents
2. A match requires the SAME SYSTEM/DOMAIN and SAME underlying
   mechanism — not just a superficial shared word like "timeout"
   or "error". A payment gateway issue is NEVER the same incident
   as an HDFS DataNode issue, even if both mention "timeout"
3. If the domain differs (e.g. payments vs distributed storage vs
   OS-level), you MUST set confidence to "no_match" regardless of
   how the distance score looks
4. Only claim "high" or "medium" confidence if you would bet your
   own reputation that an on-call engineer should trust this match
5. If none match well, say confidence is "no_match" and recommend
   human escalation — a false match is WORSE than admitting uncertainty

Respond ONLY with valid JSON in this exact format:
{{
  "matched_incident_id": "INC-XXX or null",
  "matched_incident_title": "title or null",
  "confidence": "high or medium or low or no_match",
  "likely_root_cause": "your explanation",
  "suggested_fix": "your recommendation",
  "reasoning": "why you matched or didn't match this incident",
  "sources": [{{"incident_id": "INC-XXX", "title": "source incident title", "source": "source path"}}]
}}"""

    response = get_groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    raw_text = response.choices[0].message.content.strip()

    # Extract JSON (handle cases where model adds extra text)
    try:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        json_str = raw_text[start : end + 1]
        parsed = json.loads(json_str)
        diagnosis = IncidentDiagnosis(**parsed)
        if diagnosis.matched_incident_id:
            matched = next(
                (candidate for candidate in candidates if candidate["id"] == diagnosis.matched_incident_id),
                None,
            )
            if matched:
                diagnosis.sources = [
                    {
                        "incident_id": matched["id"],
                        "title": matched["title"],
                        "source": matched["source"],
                    }
                ]
        return diagnosis
    except Exception as e:
        return IncidentDiagnosis(
            matched_incident_id=None,
            matched_incident_title=None,
            confidence="no_match",
            likely_root_cause="Failed to parse diagnosis",
            suggested_fix="Manual review needed",
            reasoning=f"Parse error: {str(e)}",
        )

# ── Run on all detected anomalies from Day 2 ──────────────────
if __name__ == "__main__":
    with open("data/detected_anomalies.json") as f:
        anomalies = json.load(f)

    print(f"Diagnosing {len(anomalies)} detected anomalies...\n")

    diagnoses = []
    # Only diagnose the first 3 unique-ish anomalies to save API calls
    for i, anomaly in enumerate(anomalies[:3]):
        print(f"--- Anomaly {i+1} ---")
        print(f"Trigger: {anomaly['trigger_message'][:80]}")

        diagnosis = diagnose_anomaly(anomaly)

        print(f"Matched: {diagnosis.matched_incident_id} ({diagnosis.confidence} confidence)")
        print(f"Root cause: {diagnosis.likely_root_cause}")
        print(f"Fix: {diagnosis.suggested_fix}")
        print()

        diagnoses.append({"anomaly": anomaly, "diagnosis": diagnosis.model_dump()})

    with open("data/diagnoses.json", "w") as f:
        json.dump(diagnoses, f, indent=2)

    print(f"Saved {len(diagnoses)} diagnoses to data/diagnoses.json")


def diagnose_anomaly_stream(anomaly: dict):
    """
    Same diagnosis logic as diagnose_anomaly(), but yields
    progress updates as it goes — for SSE streaming.
    """
    trigger = anomaly["trigger_message"]

    yield {"step": "retrieving", "message": "Searching incident knowledge base..."}

    candidates = retrieve_similar_incidents(trigger)

    for c in candidates:
        yield {
            "step": "candidate_found",
            "message": f"Candidate: {c['id']} — {c['title']} (distance: {c['distance']:.3f})",
        }

    best_distance = candidates[0]["distance"] if candidates else 999
    yield {"step": "guardrail_check", "message": f"Checking distance threshold ({DISTANCE_THRESHOLD})..."}

    if best_distance > DISTANCE_THRESHOLD:
        yield {
            "step": "no_match",
            "message": f"No confident match found (best distance {best_distance:.3f} exceeds threshold). Escalating to human.",
        }
        yield {
            "step": "final",
            "diagnosis": IncidentDiagnosis(
                matched_incident_id=None,
                matched_incident_title=None,
                confidence="no_match",
                likely_root_cause="No similar historical incident found in knowledge base",
                suggested_fix="Escalate to human on-call engineer",
                reasoning=f"Best candidate distance ({best_distance:.3f}) exceeds threshold ({DISTANCE_THRESHOLD}).",
            ).model_dump()
        }
        return

    yield {"step": "generating", "message": "Generating diagnosis with LLM..."}

    diagnosis = diagnose_anomaly(anomaly)

    yield {"step": "root_cause", "message": f"Root cause: {diagnosis.likely_root_cause}"}
    yield {"step": "fix", "message": f"Suggested fix: {diagnosis.suggested_fix}"}
    yield {"step": "final", "diagnosis": diagnosis.model_dump()}
