import json
import traceback
from datetime import datetime
from difflib import SequenceMatcher
from openai import AsyncOpenAI
from huggingface_hub import InferenceClient

import api_client
from config import (
    GEMINI_API_KEY, GEMINI_MODEL,
    OPENROUTER_API_KEY, OPENROUTER_MODEL,
    GROQ_API_KEY, GROQ_MODEL,
    HF_API_KEY, HF_BASE_URL, HF_MODEL,
    OLLAMA_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL,
)
from tools import get_tools_for_role

gemini_client = AsyncOpenAI(api_key=GEMINI_API_KEY, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
openrouter_client = AsyncOpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
groq_client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
hf_client = AsyncOpenAI(api_key=HF_API_KEY, base_url=HF_BASE_URL)
hf_free_client = InferenceClient(model=HF_MODEL, token=HF_API_KEY or None)
ollama_client = AsyncOpenAI(api_key=OLLAMA_API_KEY, base_url=OLLAMA_BASE_URL)

MAX_TOOL_ROUNDS = 6
MAX_ROUTER_CONTEXT = 8

async def _chat_completion_with_fallbacks(messages, tools=None, tool_choice="auto", **kwargs):
    clients = [
        (gemini_client, GEMINI_MODEL, "Gemini"),
        (openrouter_client, OPENROUTER_MODEL, "OpenRouter"),
        (groq_client, GROQ_MODEL, "Groq"),
        (ollama_client, OLLAMA_MODEL, "Ollama")
    ]
    
    for client, model, name in clients:
        try:
            req_kwargs = {"model": model, "messages": messages, **kwargs}
            if tools:
                req_kwargs["tools"] = tools
                req_kwargs["tool_choice"] = tool_choice
            
            # OpenRouter requires removing parallel_tool_calls for some models, but we'll try to keep it general
            if name == "Groq" and tools:
                req_kwargs["parallel_tool_calls"] = False
                
            return await client.chat.completions.create(**req_kwargs), client, model
        except Exception as e:
            print(f"[{name} Error] {e}")
            continue
            
    raise Exception("All fallback models failed.")
