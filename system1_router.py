import os
import aiohttp
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI
from config import GROQ_API_KEY, GROQ_PRIMARY_MODEL

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY", "")
SYSTEM1_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"

groq_client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

async def _query_system1(text: str, candidate_labels: list[str]) -> str:
    """
    Zero-shot classification acting as a non-autoregressive System 1 router.
    Executes a single forward pass to return the highest probability label.
    """
    if not HF_API_KEY:
        return await _fallback_llm_match(text, candidate_labels)

    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {
        "inputs": text,
        "parameters": {"candidate_labels": candidate_labels}
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SYSTEM1_API_URL, headers=headers, json=payload, timeout=5) as response:
                response.raise_for_status()
                data = await response.json()
                
                if isinstance(data, dict) and "labels" in data:
                    best_label = data["labels"][0]
                    score = data["scores"][0]
                    print(f"[System 1 Router] Picked '{best_label}' with confidence {score:.2f}")
                    if score < 0.3:
                        return await _fallback_llm_match(text, candidate_labels)
                    return best_label
                    
                elif isinstance(data, list) and len(data) > 0 and "label" in data[0]:
                     return data[0]["label"]
                     
    except Exception as e:
        print(f"[System 1 Error] {e}")
        return await _fallback_llm_match(text, candidate_labels)

async def _fallback_llm_match(text: str, candidate_labels: list[str]) -> str:
    """
    Fallback to a lightweight LLM call to pick the correct label/tool when the zero-shot classifier fails.
    """
    try:
        prompt = f"Given the user's message: '{text}'\n\nWhich of the following categories/tools best matches the intent?\n{', '.join(candidate_labels)}\n\nRespond ONLY with the exact matching label name, nothing else."
        resp = await groq_client.chat.completions.create(
            model=GROQ_PRIMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=20
        )
        content = (resp.choices[0].message.content or "").strip()
        for label in candidate_labels:
            if label.lower() in content.lower():
                return label
    except Exception as e:
        print(f"[LLM Fallback Error] {e}")
        
    # Last resort fallback: matching words
    text_lower = text.lower()
    best_match = candidate_labels[-1]
    max_matches = 0
    for label in candidate_labels:
        clean_label = label.replace("_", " ")
        matches = sum(1 for word in clean_label.split() if len(word) > 3 and word in text_lower)
        if matches > max_matches:
            max_matches = matches
            best_match = label
            
    return best_match

async def fast_intent_classification(messages: list[dict]) -> str:
    latest_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    
    semantic_labels = [
        "tool_use", 
        "health_advice", 
        "general_chat"
    ]
    
    res = await _query_system1(latest_msg, semantic_labels)
    
    if "tool" in res: return "tool"
    if "health" in res: return "health"
    return "general"

async def fast_tool_selection(messages: list[dict], available_tools: list[dict]) -> str:
    latest_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    
    tool_names = [t["function"]["name"] for t in available_tools]
    if not tool_names:
        return "unknown"
        
    res = await _query_system1(latest_msg, tool_names)
    
    if res in tool_names:
        return res
    return "unknown"
