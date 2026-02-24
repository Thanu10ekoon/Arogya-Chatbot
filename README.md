# Arogya AI Chatbot

An AI-powered healthcare assistant for the Arogya mobile clinic management system. Uses the **Groq API** with fast Llama models and function-calling to fetch real-time data from backend microservices and provide intelligent, role-based responses.

## Features

- **Role-based access**: Admin, Doctor, and Patient each get different capabilities
- **Real-time data**: Fetches live data from all backend microservices (users, clinics, consultations, lab results, queues)
- **Intent detection**: Handles small talk, data queries, and analytical questions automatically
- **Data analysis**: Admins can ask predictive/analytical questions (e.g., "Will this area have more diabetic patients next year?") — the chatbot fetches bulk data and provides data-driven insights
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
- **Groq API key** from [https://console.groq.com/](https://console.groq.com/) (Free tier available)
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

Open `.env` and set your Groq API key:

```env
GROQ_API_KEY=gsk_your-actual-api-key-here
GROQ_MODEL=llama-3.3-70b-versatile
```

**Recommended Models:**
- `llama-3.3-70b-versatile` - Best for function calling with data queries (recommended)
- `llama-3.1-70b-versatile` - Alternative with good function calling
- `llama-3.1-8b-instant` - Faster but may have issues with complex function calling
- `mixtral-8x7b-32768` - Good alternative

The other settings (service URLs, port) can stay at their defaults if your backend services are running on the standard ports.

### 5. Start the chatbot server

```bash
python main.py
```

The chatbot will start on **http://localhost:8090**.

You should see:
```
🤖 Arogya Chatbot starting on port 8090...
INFO:     Uvicorn running on http://0.0.0.0:8090
```

### 6. Verify it's running

Open a browser or use curl:
```bash
curl http://localhost:8090/health
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
| `GROQ_API_KEY` | (required) | Your Groq API key from console.groq.com (free tier available) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model to use - recommended: `llama-3.3-70b-versatile` or `llama-3.1-70b-versatile` for best function calling |
| `USER_SERVICE_URL` | `http://localhost:8081` | User service base URL |
| `CLINIC_SERVICE_URL` | `http://localhost:8082` | Clinic service base URL |
| `QUEUE_SERVICE_URL` | `http://localhost:8085` | Queue service base URL |
| `CONSULTATION_SERVICE_URL` | `http://localhost:8086` | Consultation service base URL |
| `MEDICAL_RECORDS_SERVICE_URL` | `http://localhost:8087` | Medical records service base URL |
| `CHATBOT_PORT` | `8090` | Port the chatbot server runs on |

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
