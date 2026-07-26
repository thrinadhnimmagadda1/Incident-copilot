import json
import chromadb
from sentence_transformers import SentenceTransformer

# Load incidents
with open("data/incidents.json") as f:
    incidents = json.load(f)

# Setup ChromaDB
client = chromadb.PersistentClient(path="./chroma_incidents")
collection = client.get_or_create_collection("incident_history")

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# Build searchable text for each incident — combine the fields
# that matter for matching a NEW anomaly to a PAST one
documents = []
metadatas = []
ids = []

for inc in incidents:
    # This is what gets embedded and searched against
    searchable_text = f"""
System: {inc['system']}
Symptoms: {inc['symptoms']}
Log pattern: {inc['log_pattern']}
Root cause: {inc['root_cause']}
"""
    documents.append(searchable_text)
    metadatas.append({
        "id": inc["id"],
        "title": inc["title"],
        "system": inc["system"],
        "root_cause": inc["root_cause"],
        "fix": inc["fix"],
        "severity": inc["severity"],
        "resolution_time_minutes": inc["resolution_time_minutes"]
    })
    ids.append(inc["id"])

embeddings = embedding_model.encode(documents).tolist()

collection.upsert(
    documents=documents,
    embeddings=embeddings,
    metadatas=metadatas,
    ids=ids
)

print(f"Loaded {len(incidents)} incidents into ChromaDB")
print(f"Collection count: {collection.count()}")