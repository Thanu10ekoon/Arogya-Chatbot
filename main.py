"""
Arogya Chatbot — FastAPI server.
Provides a /chat endpoint consumed by the frontend widget.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import chat_engine
import memory
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


class ClearMemoryRequest(BaseModel):
    user_id: int


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "arogya-chatbot"}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    # Validate role
    if req.user_role.lower() not in ("admin", "doctor", "patient"):
        raise HTTPException(status_code=403, detail="Chatbot is not available for this role.")

    # Extract the latest user message from the request
    latest_msg = req.messages[-1].content if req.messages else ""
    if not latest_msg:
        raise HTTPException(status_code=400, detail="No message provided.")

    # Load conversation history from server-side memory
    history = memory.get_chat_history(req.user_id)

    # Combine: persisted history + new user message
    openai_messages = history + [{"role": "user", "content": latest_msg}]

    try:
        reply = await chat_engine.chat(
            messages=openai_messages,
            role=req.user_role,
            user_id=req.user_id,
        )

        # Persist the exchange to server-side memory
        await memory.save_interaction(req.user_id, latest_msg, reply)

        return ChatResponse(reply=reply)
    except Exception as e:
        print(f"[Chat Error] {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.post("/chat/clear")
async def clear_chat(req: ClearMemoryRequest):
    """Clear conversation memory for a user (e.g. on logout or new session)."""
    memory.clear_memory(req.user_id)
    return {"status": "ok", "message": "Chat memory cleared."}


@app.get("/chat/history")
async def get_history(user_id: int):
    """Retrieve the current conversation history for a user."""
    history = memory.get_chat_history(user_id)
    return {"user_id": user_id, "messages": history}


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print(f"🤖 Arogya Chatbot starting on port {CHATBOT_PORT}...")
    uvicorn.run("main:app", host="127.0.0.1", port=CHATBOT_PORT, reload=True)
