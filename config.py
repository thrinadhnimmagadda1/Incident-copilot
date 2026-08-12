"""Environment-based configuration shared by all services."""

import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "service-logs")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_incidents")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "3"))
DISTANCE_THRESHOLD = float(os.getenv("DISTANCE_THRESHOLD", "1.2"))
ANOMALY_WINDOW_SECONDS = int(os.getenv("ANOMALY_WINDOW_SECONDS", "5"))
ANOMALY_SPIKE_THRESHOLD = int(os.getenv("ANOMALY_SPIKE_THRESHOLD", "5"))
ANOMALY_COOLDOWN_SECONDS = int(os.getenv("ANOMALY_COOLDOWN_SECONDS", "30"))
