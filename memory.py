"""
Server-side conversation memory using LangChain.

Provides per-user conversation history with automatic summarization
of older messages to stay within token limits.
"""

import asyncio
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import GEMINI_API_KEY, GEMINI_MODEL

MAX_MEMORY_TOKENS = 1200
KEEP_LAST_MESSAGES = 6


@dataclass
class UserMemory:
    summary: str = ""
    messages: list[dict] = field(default_factory=list)


# In-memory store: user_id (str) → UserMemory
_memories: dict[str, UserMemory] = {}


def _create_llm():
    """Create an LLM instance used for summarizing old messages."""
    return ChatOpenAI(
        api_key=GEMINI_API_KEY,
        model=GEMINI_MODEL,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        temperature=0,
    )


def _get_memory(user_id: int) -> UserMemory:
    """Get or create a memory instance for the given user."""
    key = str(user_id)
    if key not in _memories:
        _memories[key] = UserMemory()
    return _memories[key]


def _estimate_tokens(text: str) -> int:
    """Rough token estimator to avoid model-specific tokenizers."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _messages_to_text(messages: list[dict]) -> str:
    lines = []
    for msg in messages:
        role = msg.get("role") or "user"
        content = msg.get("content") or ""
        if role == "assistant":
            lines.append(f"Assistant: {content}")
        else:
            lines.append(f"User: {content}")
    return "\n".join(lines)


def _summarize_messages(existing_summary: str, messages: list[dict]) -> str:
    if not messages:
        return existing_summary

    system_prompt = (
        "Summarize the conversation for future context. "
        "Keep key facts, entities, preferences, and decisions. "
        "Be concise and factual."
    )

    user_prompt = (
        f"Existing summary:\n{existing_summary}\n\n"
        f"New messages:\n{_messages_to_text(messages)}"
    )

    llm = _create_llm()
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    summary = (response.content or "").strip()
    return summary or existing_summary


def _total_tokens(summary: str, messages: list[dict]) -> int:
    total = _estimate_tokens(summary)
    for msg in messages:
        total += _estimate_tokens(msg.get("content") or "")
    return total


def get_chat_history(user_id: int) -> list[dict]:
    """
    Load conversation history for a user as OpenAI-format messages.

    Returns a list of {"role": "user"|"assistant", "content": "..."} dicts.
    Older messages are automatically summarized into a system message
    when the token limit is exceeded.
    """
    memory = _get_memory(user_id)
    lc_messages = memory.messages

    result: list[dict] = []

    # If there's a running summary, inject it so the LLM has context
    if memory.summary:
        result.append({
            "role": "system",
            "content": f"Summary of earlier conversation:\n{memory.summary}",
        })

    for msg in lc_messages:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and content:
            result.append({"role": role, "content": content})

    return result


def _append_and_summarize(user_id: int, user_message: str, assistant_message: str):
    memory = _get_memory(user_id)
    memory.messages.append({"role": "user", "content": user_message})
    memory.messages.append({"role": "assistant", "content": assistant_message})

    if _total_tokens(memory.summary, memory.messages) <= MAX_MEMORY_TOKENS:
        return

    if len(memory.messages) <= KEEP_LAST_MESSAGES:
        summary = _summarize_messages(memory.summary, memory.messages)
        memory.summary = summary
        memory.messages = []
        return

    to_summarize = memory.messages[:-KEEP_LAST_MESSAGES]
    keep = memory.messages[-KEEP_LAST_MESSAGES:]
    memory.summary = _summarize_messages(memory.summary, to_summarize)
    memory.messages = keep


async def save_interaction(user_id: int, user_message: str, assistant_message: str):
    """Save a user-assistant exchange to memory.

    When the approximate token budget is exceeded, older messages are
    summarized into a compact system summary using Groq.
    """
    await asyncio.to_thread(
        _append_and_summarize,
        user_id,
        user_message,
        assistant_message,
    )


def clear_memory(user_id: int):
    """Clear conversation memory for a specific user."""
    key = str(user_id)
    if key in _memories:
        del _memories[key]


def clear_all():
    """Clear all users' conversation memories."""
    _memories.clear()

