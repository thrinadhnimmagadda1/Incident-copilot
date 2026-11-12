"""Environment-based configuration shared by all services."""

import os

from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "service-logs")
LOG_SOURCE = os.getenv("LOG_SOURCE", "OpenStack")
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", f"data/{LOG_SOURCE}_2k.log")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_incidents")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "3"))
DISTANCE_THRESHOLD = float(os.getenv("DISTANCE_THRESHOLD", "1.2"))
ANOMALY_WINDOW_SECONDS = int(os.getenv("ANOMALY_WINDOW_SECONDS", "5"))
ANOMALY_SPIKE_THRESHOLD = int(os.getenv("ANOMALY_SPIKE_THRESHOLD", "5"))
ANOMALY_COOLDOWN_SECONDS = int(os.getenv("ANOMALY_COOLDOWN_SECONDS", "30"))
