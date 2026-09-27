# Arogya AI Chatbot

An AI-powered healthcare assistant for the Arogya mobile clinic management system. Uses the **Groq API** with fast Llama models and function-calling to fetch real-time data from backend microservices and provide intelligent, role-based responses.

## Features

- **Role-based access**: Admin, Doctor, and Patient each get different capabilities
- **Intent routing**: Groq decides if a query needs tools, health knowledge, or general response
- **Real-time data**: Fetches live data from all backend microservices (users, clinics, consultations, lab results, queues)
- **Intent detection**: Handles small talk, data queries, and analytical questions automatically
- **Data analysis**: Admins can ask predictive/analytical questions (e.g., "Will this area have more diabetic patients next year?") — the chatbot fetches bulk data and provides data-driven insights
- **Medical Q&A Specialization**: When a patient asks a health or symptom-related question, the chatbot automatically routes the request to a fine-tuned medical LLM hosted on Hugging Face Spaces (`Thanu10/Arogya-Medical-Chat`) via Gradio.
- **Secure**: Patients can only access their own data; role enforcement is applied server-side

## Role Capabilities

| Capability | Admin | Doctor | Patient |
|---|:---:|:---:|:---:|
| View all patients | ✅ | — | — |
| View all doctors | ✅ | — | — |
| View all users | ✅ | — | — |
| View any patient's details | ✅ | ✅ | Own only |
| View clinics | ✅ | ✅ | ✅ |
| View clinic queue | ✅ | ✅ | — |
| View consultations | All | Own patients | Own only |
| View lab results | All | By patient | Own only |
| Analytical queries | ✅ | — | — |
| Own profile | ✅ | ✅ | ✅ |

## Prerequisites

- **Python 3.11+**
- **Hugging Face API token** from [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (for the fine-tuned model)
- **Groq API key** from [https://console.groq.com/](https://console.groq.com/) (fallback)
- Backend microservices running (user-service, clinic-service, etc.)

## Setup

### 1. Navigate to the chatbot directory

```bash
cd Arogya-Chatbot
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

**Activate it:**

- **Windows:** `venv\Scripts\activate`
- **Linux/Mac:** `source venv/bin/activate`

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set your API keys:

```env
# Primary Provider (Gemini)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash

# Fallback Providers
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=qwen/qwen-2.5-72b-instruct

GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.3-70b-versatile

OLLAMA_API_KEY=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3
```

**Model Fallback Architecture:**
The chatbot uses a robust fallback mechanism using the `langchain-openai` interface. It will automatically try providers in the following sequence if rate limits or errors occur:
1. **Gemini** (Primary)
2. **OpenRouter** (Fallback 1)
3. **Groq** (Fallback 2)
4. **Ollama** (Local Fallback 3)

### 5. Start the chatbot server

```bash
python main.py
```

The chatbot will start on **http://localhost:8091**.

You should see:
```
🤖 Arogya Chatbot starting on port 8091...
INFO:     Uvicorn running on http://127.0.0.1:8091
```

### 6. Verify it's running

Open a browser or use curl:
```bash
curl http://localhost:8091/health
```

Expected response:
```json
{"status": "ok", "service": "arogya-chatbot"}
```

## Frontend Integration

The chatbot widget is already integrated into the Arogya Frontend. Once the chatbot server is running:

1. Start the frontend (`npm run dev` in `Arogya-Frontend/`)
2. Log in as any **Admin**, **Doctor**, or **Patient**
3. A chat bubble (💬) will appear in the bottom-right corner
4. Click it to open the chat panel

**Note:** The chatbot does NOT appear for Technician users.

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | (required) | Primary Gemini API Key |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Primary Model |
| `OPENROUTER_API_KEY` | (optional) | OpenRouter API Key for fallback |
| `OPENROUTER_MODEL` | `qwen/qwen-2.5-72b-instruct` | OpenRouter model |
| `GROQ_API_KEY` | (optional) | Groq API Key for fallback |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model |
| `USER_SERVICE_URL` | `http://localhost:8081` | User service base URL |
| `CLINIC_SERVICE_URL` | `http://localhost:8082` | Clinic service base URL |
| `QUEUE_SERVICE_URL` | `http://localhost:8085` | Queue service base URL |
| `CONSULTATION_SERVICE_URL` | `http://localhost:8086` | Consultation service base URL |
| `MEDICAL_RECORDS_SERVICE_URL` | `http://localhost:8087` | Medical records service base URL |
| `CHATBOT_PORT` | `8091` | Port the chatbot server runs on |

## Example Conversations

**Patient:**
```
User: "Show me my lab results"
Bot: (fetches lab results for the logged-in patient and displays them)

User: "Do I have any upcoming clinic appointments?"
Bot: (fetches available clinics and shows relevant ones)
```

**Admin:**
```
User: "How many patients do we have?"
Bot: (fetches all patients and provides a count with summary)

User: "Will the Galle district area have more diabetic patients next year?"
Bot: (fetches all patient data, analyzes chronic diseases and locations, provides a data-driven prediction)

User: "Show me all doctors and their specializations"
Bot: (fetches all doctor profiles and presents a formatted list)
```

**Doctor:**
```
User: "Show me my consultations for today"
Bot: (fetches the doctor's consultations and filters by date)

User: "What's in the queue for clinic 5?"
Bot: (fetches queue tokens for clinic 5 and displays positions/statuses)
```

## Architecture

```
┌─────────────────┐     HTTP      ┌──────────────────────┐
│  Frontend Widget │ ──────────── │  Chatbot Server      │
│  (React)         │   /chat      │  (FastAPI :8090)     │
└─────────────────┘              │                      │
                                  │  ┌────────────────┐  │
                                  │  │  Groq API      │  │
                                  │  │  (Llama LLM)   │  │
                                  │  └───────┬────────┘  │
                                  │          │           │
                                  │  ┌───────▼────────┐  │
                                  │  │  Tool Executor  │  │
                                  │  └───────┬────────┘  │
                                  └──────────┼───────────┘
                                             │
                    ┌────────────┬────────────┼───────────┬──────────────┐
                    │            │            │           │              │
              ┌─────▼───┐ ┌─────▼───┐ ┌──────▼──┐ ┌─────▼────┐ ┌──────▼──────┐
              │ User    │ │ Clinic  │ │ Queue   │ │ Consult  │ │ Med Records │
              │ :8081   │ │ :8082   │ │ :8085   │ │ :8086    │ │ :8087       │
              └─────────┘ └─────────┘ └─────────┘ └──────────┘ └─────────────┘
```

## Troubleshooting

| Issue | Solution |
|---|---|
| `GROQ_API_KEY not set` | Make sure `.env` file exists with a valid key from console.groq.com |
| `Connection refused on :8090` | Ensure the chatbot server is running (`python main.py`) |
| `Unable to connect to user service` | Ensure backend microservices are running |
| `403 Forbidden` | Only admin/doctor/patient roles can use the chatbot |
| Chat bubble doesn't appear | Must be logged in as admin, doctor, or patient (not technician) |
