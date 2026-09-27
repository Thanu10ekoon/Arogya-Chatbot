import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_PRIMARY_MODEL = os.getenv("GROQ_PRIMARY_MODEL", "qwen/qwen3.8-27b")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8081")
CLINIC_SERVICE_URL = os.getenv("CLINIC_SERVICE_URL", "http://localhost:8082")
QUEUE_SERVICE_URL = os.getenv("QUEUE_SERVICE_URL", "http://localhost:8085")
CONSULTATION_SERVICE_URL = os.getenv("CONSULTATION_SERVICE_URL", "http://localhost:8086")
MEDICAL_RECORDS_SERVICE_URL = os.getenv("MEDICAL_RECORDS_SERVICE_URL", "http://localhost:8087")

CHATBOT_PORT = int(os.getenv("CHATBOT_PORT", "8091"))
