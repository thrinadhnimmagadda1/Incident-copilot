import streamlit as st
import requests
import json

st.set_page_config(
    page_title="Incident Copilot",
    page_icon="🚨",
    layout="wide"
)

API_URL = "http://127.0.0.1:8000"

st.title("🚨 Incident Copilot")
st.caption("AI-powered production incident diagnosis using RAG over historical incidents")

# ── Sidebar: Knowledge base overview ───────────────────────────
with st.sidebar:
    st.header("Knowledge Base")
    try:
        health = requests.get(f"{API_URL}/health").json()
        st.metric("Incidents on record", health["incidents_in_knowledge_base"])
    except Exception:
        st.error("API not reachable — is Docker running?")

    st.divider()
    st.subheader("All Incidents")
    try:
        incidents = requests.get(f"{API_URL}/incidents").json()
        for inc in incidents:
            severity_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(inc["severity"], "⚪")
            st.markdown(f"{severity_color} **{inc['id']}** — {inc['title']}")
            st.caption(f"System: {inc['system']}")
    except Exception:
        st.warning("Could not load incidents")

# ── Main: Anomaly input ────────────────────────────────────────
st.subheader("Diagnose an Anomaly")

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
    diagnose_clicked = st.button("🔍 Diagnose", type="primary", use_container_width=True)

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
                stream=True
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
                    st.markdown("### Diagnosis Result")

                    confidence = final_diagnosis["confidence"]
                    conf_color = {
                        "high": "🟢", "medium": "🟡",
                        "low": "🟠", "no_match": "🔴"
                    }.get(confidence, "⚪")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric("Matched Incident", final_diagnosis["matched_incident_id"] or "None")
                    with col_b:
                        st.metric("Confidence", f"{conf_color} {confidence}")

                    if final_diagnosis["matched_incident_title"]:
                        st.info(f"**{final_diagnosis['matched_incident_title']}**")

                    st.markdown(f"**Root cause:** {final_diagnosis['likely_root_cause']}")
                    st.markdown(f"**Suggested fix:** {final_diagnosis['suggested_fix']}")

                    with st.expander("Full reasoning"):
                        st.write(final_diagnosis["reasoning"])

                    if confidence == "no_match":
                        st.warning("⚠️ No confident match — escalate to human on-call engineer.")

        except Exception as e:
            st.error(f"Error connecting to API: {e}")

elif diagnose_clicked:
    st.warning("Please enter an anomaly message first.")

# ── Footer: Evaluation results ──────────────────────────────────
st.divider()
st.subheader("System Evaluation (RAGAS)")
try:
    eval_results = requests.get(f"{API_URL}/eval-results").json()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall Accuracy", f"{eval_results['overall_accuracy']:.0%}")
    c2.metric("Refusal Accuracy", f"{eval_results['refusal_accuracy']:.0%}")
    c3.metric("Faithfulness", f"{eval_results['faithfulness']:.2f}")
    c4.metric("Answer Relevancy", f"{eval_results['answer_relevancy']:.2f}")
except Exception:
    st.info("No evaluation results found — run evaluate_diagnosis.py to generate them.")