import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY", "")
SYSTEM1_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"

def _query_system1(text: str, candidate_labels: list[str]) -> str:
    """
    Zero-shot classification acting as a non-autoregressive System 1 router.
    Executes a single forward pass to return the highest probability label.
    """
    if not HF_API_KEY:
        return _fallback_string_match(text, candidate_labels)

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
            best_label = data["labels"][0]
            score = data["scores"][0]
            print(f"[System 1 Router] Picked '{best_label}' with confidence {score:.2f}")
            return best_label
            
        elif isinstance(data, list) and len(data) > 0 and "label" in data[0]:
             return data[0]["label"]
             
    except Exception as e:
        print(f"[System 1 Error] {e}")
        return _fallback_string_match(text, candidate_labels)

def _fallback_string_match(text: str, candidate_labels: list[str]) -> str:
    text_lower = text.lower()
    
    # Intent fallback
    if "tool_use" in candidate_labels:
        if any(w in text_lower for w in ["clinic", "patient", "queue", "consult", "detail", "all", "record"]):
            return candidate_labels[0]
        if any(w in text_lower for w in ["health", "medical", "disease", "pain", "headache", "fever", "symptom", "sick", "doctor", "medicine", "pill", "hurt", "ill", "ache"]):
            return candidate_labels[1]
        return candidate_labels[2]
        
    # Tool selection fallback
    for label in candidate_labels:
        clean_label = label.replace("_", " ")
        if any(word in text_lower for word in clean_label.split() if len(word) > 3):
            return label
            
    return candidate_labels[-1]

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

def fast_tool_selection(messages: list[dict], available_tools: list[dict]) -> str:
    latest_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    
    tool_names = [t["function"]["name"] for t in available_tools]
    if not tool_names:
        return "unknown"
        
    res = _query_system1(latest_msg, tool_names)
    
    if res in tool_names:
        return res
    return "unknown"
