import json

import requests
import streamlit as st

from config import API_URL

st.set_page_config(
    page_title="Incident Copilot",
    page_icon="🚨",
    layout="wide"
)

st.title("Incident Copilot")
st.caption("AI incident commander using Kafka, real OpenStack logs, MCP tools, and human-safe recommendations")

# ── Sidebar: Knowledge base overview ───────────────────────────
with st.sidebar:
    st.header("Knowledge Base")
    try:
        health = requests.get(f"{API_URL}/health", timeout=5).json()
        st.metric("Incidents on record", health["incidents_in_knowledge_base"])
    except Exception:
        st.error("API not reachable — is Docker running?")

    st.divider()
    st.subheader("All Incidents")
    try:
        incidents = requests.get(f"{API_URL}/incidents", timeout=5).json()
        for inc in incidents:
            severity_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(inc["severity"], "⚪")
            st.markdown(f"{severity_color} **{inc['id']}** — {inc['title']}")
            st.caption(f"System: {inc['system']}")
    except Exception:
        st.warning("Could not load incidents")

# ── Main: Anomaly input ────────────────────────────────────────
st.subheader("Investigate an Anomaly")

example_anomalies = {
    "HDFS DataNode exception (real)": "10.251.30.85:50010:Got exception while serving blk_-2918118818249673980",
    "OpenStack image cache warning (real)": "Unknown base file: /var/lib/nova/instances/_base/a489c868f0c37da93b76227c91bb03908ac0e742",
    "Unrelated payment gateway (should reject)": "Payment gateway returned HTTP 503 for checkout requests, credit card processor timeout after 30s",
    "Custom input": ""
}

choice = st.selectbox("Choose an example or write your own:", list(example_anomalies.keys()))
default_text = example_anomalies[choice]

trigger_message = st.text_area(
    "Anomaly trigger message:",
    value=default_text,
    height=80
)

col1, col2 = st.columns([1, 4])
with col1:
    diagnose_clicked = st.button("Investigate", type="primary", use_container_width=True)


def show_diagnosis(final_diagnosis):
    st.markdown("### Diagnosis Result")

    confidence = final_diagnosis["confidence"]
    conf_color = {
        "high": "Green",
        "medium": "Yellow",
        "low": "Orange",
        "no_match": "Needs review",
    }.get(confidence, "Unknown")

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("Matched Incident", final_diagnosis["matched_incident_id"] or "None")
    with col_b:
        st.metric("Confidence", f"{conf_color}: {confidence}")

    if final_diagnosis["matched_incident_title"]:
        st.info(f"**{final_diagnosis['matched_incident_title']}**")

    st.markdown(f"**Root cause:** {final_diagnosis['likely_root_cause']}")
    st.markdown(f"**Suggested fix:** {final_diagnosis['suggested_fix']}")

    with st.expander("Full reasoning"):
        st.write(final_diagnosis["reasoning"])

    sources = final_diagnosis.get("sources") or []
    if sources:
        st.markdown("**Evidence sources:**")
        for source in sources:
            st.caption(
                f"{source['incident_id']} - {source['title']} ({source['source']})"
            )

    if confidence == "no_match":
        st.warning("No confident match. Escalate to a human on-call engineer.")


def show_agent_investigation(investigation):
    st.markdown("### AI Agent Investigation")

    st.markdown("**Agent steps**")
    for step in investigation["agent_steps"]:
        st.write(f"- {step}")

    st.markdown("**MCP tool evidence**")
    for item in investigation["evidence"]:
        with st.expander(f"{item['tool']}: {item['summary']}"):
            st.json(item["result"])

    ticket = investigation["ticket"]
    st.markdown("### Human Approval Ticket")
    col_a, col_b = st.columns(2)
    col_a.metric("Approval required", "Yes" if ticket["requires_human_approval"] else "No")
    col_b.metric("Ticket confidence", ticket["confidence"])
    st.markdown(f"**Title:** {ticket['title']}")
    st.markdown(f"**Suggested action:** {ticket['suggested_fix']}")

# ── Live streaming diagnosis ────────────────────────────────────
if diagnose_clicked and trigger_message.strip():
    progress_container = st.container()
    result_container = st.empty()

    with progress_container:
        st.markdown("### Live Diagnosis Feed")
        log_box = st.empty()
        logs = []

        try:
            response = requests.post(
                f"{API_URL}/diagnose/stream",
                json={"trigger_message": trigger_message, "trigger_raw": trigger_message},
                stream=True,
                timeout=60,
            )

            final_diagnosis = None

            for line in response.iter_lines():
                if line:
                    line_text = line.decode("utf-8")
                    if line_text.startswith("data: "):
                        payload = line_text[6:]
                        if payload == "[DONE]":
                            break
                        event = json.loads(payload)

                        if event.get("step") == "final":
                            final_diagnosis = event["diagnosis"]
                        else:
                            logs.append(f"**{event['step']}**: {event['message']}")
                            log_box.markdown("\n\n".join(logs))

            # ── Show final structured result ────────────────────
            if final_diagnosis:
                with result_container.container():
                    show_diagnosis(final_diagnosis)

                    agent_response = requests.post(
                        f"{API_URL}/agent/investigate",
                        json={"trigger_message": trigger_message, "trigger_raw": trigger_message},
                        timeout=60,
                    )
                    agent_response.raise_for_status()
                    show_agent_investigation(agent_response.json())

        except Exception as e:
            st.error(f"Error connecting to API: {e}")

elif diagnose_clicked:
    st.warning("Please enter an anomaly message first.")

# ── Footer: Evaluation results ──────────────────────────────────
st.divider()
st.subheader("Offline Retrieval Benchmark")
try:
    retrieval_results = requests.get(f"{API_URL}/retrieval-eval-results", timeout=5).json()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Benchmark Cases", retrieval_results["benchmark_cases"])
    c2.metric("Recall@1", f"{retrieval_results['retrieval_recall_at_1']:.0%}")
    c3.metric("Match F1", f"{retrieval_results['match_f1']:.1%}")
    c4.metric("False Positive Rate", f"{retrieval_results['false_positive_rate']:.1%}")

    c5, c6, c7 = st.columns(3)
    c5.metric("Match Precision", f"{retrieval_results['match_precision']:.1%}")
    c6.metric("Match Recall", f"{retrieval_results['match_recall']:.1%}")
    c7.metric("Warm P95 Retrieval", f"{retrieval_results['warm_p95_retrieval_latency_ms']:.0f} ms")
except Exception:
    st.info("No retrieval benchmark found — run evaluate_retrieval.py to generate it.")

st.subheader("Saved Full-LLM Evaluation (RAGAS)")
try:
    eval_results = requests.get(f"{API_URL}/eval-results", timeout=5).json()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall Accuracy", f"{eval_results['overall_accuracy']:.0%}")
    c2.metric("Refusal Accuracy", f"{eval_results['refusal_accuracy']:.0%}")
    c3.metric("Faithfulness", f"{eval_results['faithfulness']:.2f}")
    c4.metric("Answer Relevancy", f"{eval_results['answer_relevancy']:.2f}")
except Exception:
    st.info("No evaluation results found — run evaluate_diagnosis.py to generate them.")
