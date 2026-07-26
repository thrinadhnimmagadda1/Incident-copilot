"""
Evaluate the incident diagnosis system using:
1. Custom accuracy check — did it match the RIGHT incident
   (or correctly say no_match)?
2. RAGAS faithfulness — is the diagnosis's reasoning grounded
   in the actual retrieved incident data, or hallucinated?
"""
import json
import os
from dotenv import load_dotenv
from diagnose import diagnose_anomaly, retrieve_similar_incidents
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.run_config import RunConfig
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings

load_dotenv()

with open("data/eval_set.json") as f:
    test_cases = json.load(f)

print(f"Evaluating {len(test_cases)} test cases...\n")

# Separate matched cases (evaluate with RAGAS) from refusal
# cases (evaluate separately — RAGAS isn't designed for these)
correct = 0
ragas_eval_data = {
    "question": [], "answer": [], "contexts": [], "ground_truth": []
}
refusal_correct = 0
refusal_total = 0

for i, case in enumerate(test_cases):
    anomaly = {"trigger_message": case["trigger"], "trigger_raw": case["trigger"]}
    diagnosis = diagnose_anomaly(anomaly)
    candidates = retrieve_similar_incidents(case["trigger"])

    is_correct = False
    if case["expected_incident"] is None:
        is_correct = diagnosis.confidence == "no_match"
        refusal_total += 1
        refusal_correct += is_correct
    else:
        is_correct = diagnosis.matched_incident_id == case["expected_incident"]

    correct += is_correct
    status = "PASS" if is_correct else "FAIL"
    print(f"[{status}] Test {i+1}: expected={case['expected_incident']}, got={diagnosis.matched_incident_id} ({diagnosis.confidence})")

    if case["expected_incident"] is not None:
        ragas_eval_data["question"].append(case["trigger"])
        ragas_eval_data["answer"].append(
            f"Matched: {diagnosis.matched_incident_id}. Root cause: {diagnosis.likely_root_cause}. Fix: {diagnosis.suggested_fix}"
        )
        context_texts = [
            f"{c['title']}: {c['root_cause']} Fix applied: {c['fix']}" for c in candidates[:2]
        ]
        ragas_eval_data["contexts"].append(context_texts)
        ragas_eval_data["ground_truth"].append(case["ground_truth"])

accuracy = correct / len(test_cases)
refusal_accuracy = refusal_correct / refusal_total if refusal_total else None
print(f"\n--- Overall accuracy: {correct}/{len(test_cases)} = {accuracy:.1%} ---")
print(f"--- Refusal accuracy (no_match cases): {refusal_correct}/{refusal_total} = {refusal_accuracy:.1%} ---\n")

print("Running RAGAS evaluation on matched cases only (this makes LLM calls, ~1-2 min)...\n")

dataset = Dataset.from_dict(ragas_eval_data)

llm = LangchainLLMWrapper(ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    max_tokens=1024
))
embeddings = LangchainEmbeddingsWrapper(
    HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
)

result = evaluate(
    dataset=dataset,
    metrics=[faithfulness, answer_relevancy],
    llm=llm,
    embeddings=embeddings,
    run_config=RunConfig(
        timeout=120,
        max_retries=3,
        max_workers=1
    )
)

df = result.to_pandas()
avg_faithfulness = df["faithfulness"].mean()
avg_relevancy = df["answer_relevancy"].mean()

print("\n" + "="*60)
print("RAGAS EVALUATION RESULTS (matched cases only)")
print("="*60)
print(f"Overall accuracy:        {accuracy:.1%}")
print(f"Refusal accuracy:        {refusal_accuracy:.1%}")
print(f"Faithfulness:            {avg_faithfulness:.3f}")
print(f"Answer Relevancy:        {avg_relevancy:.3f}")
print("="*60)

print("\nPer-test-case breakdown (matched cases only):")
for i, row in df.iterrows():
    print(f"  Test {i+1}: faithfulness={row['faithfulness']:.2f}, relevancy={row['answer_relevancy']:.2f}")

summary = {
    "overall_accuracy": accuracy,
    "refusal_accuracy": refusal_accuracy,
    "faithfulness": float(avg_faithfulness),
    "answer_relevancy": float(avg_relevancy),
    "test_case_count": len(test_cases)
}
with open("data/eval_results.json", "w") as f:
    json.dump(summary, f, indent=2)
print("\nSaved to data/eval_results.json")