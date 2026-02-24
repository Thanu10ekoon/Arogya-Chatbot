"""
Arogya Chatbot — FastAPI server.
Provides a /chat endpoint consumed by the frontend widget.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import chat_engine
from config import CHATBOT_PORT

app = FastAPI(title="Arogya Chatbot", version="1.0.0")

# Allow frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ────────────────────────────────────────────────

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    user_id: int
    user_role: str  # "admin" | "doctor" | "patient"


class ChatResponse(BaseModel):
    reply: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "arogya-chatbot"}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    # Validate role
    if req.user_role.lower() not in ("admin", "doctor", "patient"):
        raise HTTPException(status_code=403, detail="Chatbot is not available for this role.")

    # Convert messages to OpenAI format
    openai_messages = [{"role": m.role, "content": m.content} for m in req.messages]

    try:
        reply = await chat_engine.chat(
            messages=openai_messages,
            role=req.user_role,
            user_id=req.user_id,
        )
        return ChatResponse(reply=reply)
    except Exception as e:
        print(f"[Chat Error] {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print(f"🤖 Arogya Chatbot starting on port {CHATBOT_PORT}...")
    uvicorn.run("main:app", host="0.0.0.0", port=CHATBOT_PORT, reload=True)
