"""
Server-side conversation memory using LangChain.

Provides per-user conversation history with automatic summarization
of older messages to stay within token limits.
"""

import asyncio

from langchain.memory import ConversationSummaryBufferMemory
from langchain_core.messages import AIMessage, HumanMessage
from langchain_groq import ChatGroq

from config import GROQ_API_KEY, GROQ_MODEL

# In-memory store: user_id (str) → ConversationSummaryBufferMemory
_memories: dict[str, ConversationSummaryBufferMemory] = {}


def _create_llm():
    """Create a Groq LLM instance used for summarizing old messages."""
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model_name=GROQ_MODEL,
        temperature=0,
    )


def _get_memory(user_id: int) -> ConversationSummaryBufferMemory:
    """Get or create a memory instance for the given user."""
    key = str(user_id)
    if key not in _memories:
        _memories[key] = ConversationSummaryBufferMemory(
            llm=_create_llm(),
            max_token_limit=1500,
            return_messages=True,
            memory_key="history",
            human_prefix="User",
            ai_prefix="Arogya AI",
        )
    return _memories[key]


def get_chat_history(user_id: int) -> list[dict]:
    """
    Load conversation history for a user as OpenAI-format messages.

    Returns a list of {"role": "user"|"assistant", "content": "..."} dicts.
    Older messages are automatically summarized into a system message
    when the token limit is exceeded.
    """
    memory = _get_memory(user_id)
    variables = memory.load_memory_variables({})
    lc_messages = variables.get("history", [])

    result: list[dict] = []

    # If there's a running summary, inject it so the LLM has context
    if memory.moving_summary_buffer:
        result.append({
            "role": "system",
            "content": f"Summary of earlier conversation:\n{memory.moving_summary_buffer}",
        })

    for msg in lc_messages:
        if isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})

    return result


async def save_interaction(user_id: int, user_message: str, assistant_message: str):
    """Save a user↔assistant exchange to memory.

    When the buffer exceeds *max_token_limit*, LangChain automatically
    summarises the oldest messages using the Groq LLM.
    """
    memory = _get_memory(user_id)
    # save_context is synchronous and may invoke the LLM for summarization,
    # so we run it in a thread to avoid blocking the event loop.
    await asyncio.to_thread(
        memory.save_context,
        {"input": user_message},
        {"output": assistant_message},
    )


def clear_memory(user_id: int):
    """Clear conversation memory for a specific user."""
    key = str(user_id)
    if key in _memories:
        _memories[key].clear()
        del _memories[key]


def clear_all():
    """Clear all users' conversation memories."""
    _memories.clear()
