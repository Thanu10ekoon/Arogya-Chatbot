import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY", "")
SYSTEM1_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"

def _query_system1_top_k(text: str, candidate_labels: list[str], k: int = 5) -> list[str]:
    """
    Zero-shot classification acting as a non-autoregressive System 1 router.
    Returns the top K highest probability labels to give the generative LLM a filtered but safe subset.
    """
    if not HF_API_KEY:
        return _fallback_string_match_top_k(text, candidate_labels, k)

    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {
        "inputs": text,
        "parameters": {"candidate_labels": candidate_labels}
    }
    
    try:
        response = requests.post(SYSTEM1_API_URL, headers=headers, json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, dict) and "labels" in data:
            best_labels = data["labels"][:k]
            print(f"[System 1 Router] Picked top {k} tools: {best_labels}")
            return best_labels
            
    except Exception as e:
        print(f"[System 1 Error] {e}")
    return _fallback_string_match_top_k(text, candidate_labels, k)

def _fallback_string_match_top_k(text: str, candidate_labels: list[str], k: int) -> list[str]:
    text_lower = text.lower()
    matches = []
    
    for label in candidate_labels:
        clean_label = label.replace("_", " ")
        if any(word in text_lower for word in clean_label.split() if len(word) > 3):
            matches.append(label)
            
    if not matches:
        return candidate_labels[:k]
    return matches[:k]

def fast_intent_classification(messages: list[dict]) -> str:
    latest_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    
    semantic_labels = [
        "tool_use", 
        "health_advice", 
        "general_chat"
    ]
    
    res = _query_system1(latest_msg, semantic_labels)
    
    if "tool" in res: return "tool"
    if "health" in res: return "health"
    return "general"

def fast_tool_selection(messages: list[dict], available_tools: list[dict]) -> list[str]:
    latest_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    
    tool_names = [t["function"]["name"] for t in available_tools]
    if not tool_names:
        return []
        
    return _query_system1_top_k(latest_msg, tool_names, k=5)
