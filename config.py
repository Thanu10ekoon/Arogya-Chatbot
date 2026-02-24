import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8081")
CLINIC_SERVICE_URL = os.getenv("CLINIC_SERVICE_URL", "http://localhost:8082")
QUEUE_SERVICE_URL = os.getenv("QUEUE_SERVICE_URL", "http://localhost:8085")
CONSULTATION_SERVICE_URL = os.getenv("CONSULTATION_SERVICE_URL", "http://localhost:8086")
MEDICAL_RECORDS_SERVICE_URL = os.getenv("MEDICAL_RECORDS_SERVICE_URL", "http://localhost:8087")

CHATBOT_PORT = int(os.getenv("CHATBOT_PORT", "8090"))
