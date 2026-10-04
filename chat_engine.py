"""
Core chat engine for Arogya AI Chatbot.
Uses Groq (qwen/qwen3.8-27b primary) with Gemini fallback.
Supports tool-calling (function calling) for real-time backend data.
"""

import json
import re
import traceback
from datetime import datetime
from difflib import SequenceMatcher
from openai import AsyncOpenAI

import api_client
from config import (
    GROQ_API_KEY,
    GROQ_PRIMARY_MODEL,
    GROQ_FALLBACK_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
)
from tools import get_tools_for_role

# ---------------------------------------------------------------------------
# LLM Clients
# ---------------------------------------------------------------------------
groq_client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

gemini_client = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

MAX_TOOL_ROUNDS = 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _is_rate_limit(err: str) -> bool:
    msg = err.lower()
    return "rate limit" in msg or "rate_limit" in msg or "429" in msg


def _is_quota(err: str) -> bool:
    msg = err.lower()
    return "quota" in msg or "resource_exhausted" in msg or "429" in msg


_NARRATION_RE = re.compile(
    r"^(I('m| will| am going to| shall|'ll) (call|fetch|get|check|look up|retrieve|use)|"
    r"Let me (call|fetch|get|check|look up|retrieve)|Calling \w+).*?\n?",
    re.IGNORECASE | re.MULTILINE,
)

_FAKE_TOOL_RE = re.compile(
    r"(<function=\w+>|get_\w+\([^)]*\)\s*$)",
    re.IGNORECASE | re.MULTILINE,
)


def _clean_response(text: str) -> str:
    if not text:
        return text
    text = _NARRATION_RE.sub("", text).strip()
    return text


def _is_fake_tool_call(text: str) -> bool:
    return bool(text and _FAKE_TOOL_RE.search(text))


# ---------------------------------------------------------------------------
# LLM call with provider fallback chain
# ---------------------------------------------------------------------------
async def _llm_call(**kwargs) -> object:
    """
    Try Groq primary -> Groq 120b fallback -> Gemini.
    Retries on rate limits, quota errors, tool_use_failed, and model errors.
    """
    # Fallback chain: Primary -> Fallback -> Gemini
    providers = [
        (groq_client, GROQ_PRIMARY_MODEL, "Groq-primary"),
        (groq_client, GROQ_FALLBACK_MODEL, "Groq-fallback"),
        (gemini_client, GEMINI_MODEL, "Gemini"),
    ]

    last_err = None
    for client, model, name in providers:
        if not model or not (client.api_key or "").strip():
            continue
        try:
            req = dict(kwargs)
            req["model"] = model
            # Remove parallel_tool_calls for Gemini (unsupported)
            if name == "Gemini":
                req.pop("parallel_tool_calls", None)
            response = await client.chat.completions.create(**req)
            print(f"[LLM] Used {name} ({model})")
            return response
        except Exception as e:
            err = str(e)
            print(f"[{name} Error] {err[:200]}")
            last_err = e
            # Continue to next provider on rate-limit, quota, model, or tool_use_failed errors
            err_lower = err.lower()
            should_fallback = (
                _is_rate_limit(err) or _is_quota(err)
                or "model_not_found" in err_lower
                or "model_decommissioned" in err_lower
                or "does not exist" in err_lower
                or "tool_use_failed" in err_lower
            )
            if not should_fallback:
                break

    raise RuntimeError(f"All LLM providers failed. Last error: {last_err}")


# ---------------------------------------------------------------------------
# Intent classifier
# ---------------------------------------------------------------------------
async def _classify_intent(messages: list[dict]) -> str:
    """Classify user intent as: tool | health | general"""
    system = (
        "You are a router. Output ONLY one word: tool, health, or general.\n"
        "tool = user needs live data (clinics, queues, appointments, patients, consultations, lab results, users).\n"
        "health = user asks a medical or health question (symptoms, treatments, medications, lifestyle).\n"
        "general = greetings, small talk, app navigation questions."
    )
    router_msgs = [{"role": "system", "content": system}] + messages[-6:]
    try:
        resp = await _llm_call(messages=router_msgs, temperature=0, max_tokens=5)
        label = (resp.choices[0].message.content or "general").strip().lower()
        return label if label in ("tool", "health", "general") else "general"
    except Exception:
        return "general"


# ---------------------------------------------------------------------------
# Clinic name -> ID resolver
# ---------------------------------------------------------------------------
async def _resolve_clinic_id(name: str) -> str | None:
    clinics = await api_client.get_all_clinics()
    if not isinstance(clinics, list) or not clinics:
        return None
    # Keep exact match as an optimization
    name_lower = name.lower().strip()
    for c in clinics:
        if c.get("clinicName", "").lower() == name_lower:
            return str(c["id"])
            
    # Use LLM for intelligent mapping
    try:
        clinic_list_str = "\n".join([f"ID: {c.get('id')} - Name: {c.get('clinicName')}" for c in clinics])
        prompt = f"Given the user's requested clinic name: '{name}'\n\nFind the best matching clinic from this list:\n{clinic_list_str}\n\nRespond ONLY with the exact numerical ID of the matching clinic. If no clinic is a reasonable match, respond with 'None'."
        resp = await groq_client.chat.completions.create(
            model=GROQ_PRIMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10
        )
        content = (resp.choices[0].message.content or "").strip()
        if content.isdigit():
            return content
    except Exception as e:
        print(f"[_resolve_clinic_id LLM Error] {e}")

    return None


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------
async def _execute_tool(fn_name: str, args: dict, role: str, user_id: int) -> str:
    try:
        role_lower = role.lower()

        # --- RBAC enforcement ---
        if role_lower == "patient":
            if fn_name in ("get_all_patients", "get_all_doctors", "get_all_users",
                           "get_all_technicians", "get_all_test_results",
                           "create_clinic", "update_clinic", "delete_clinic",
                           "update_consultation", "complete_consultation", "cancel_consultation",
                           "update_user", "delete_user"):
                return json.dumps({"error": "Access denied. Patients cannot perform this action."})
            if fn_name == "create_consultation":
                # Force patient to only book for themselves
                args["patientId"] = user_id
        elif role_lower == "doctor":
            if fn_name in ("create_clinic", "delete_clinic", "update_user", "delete_user"):
                return json.dumps({"error": "Access denied. Doctors cannot perform this administrative action."})
                
        if role_lower == "patient":
            if fn_name == "get_consultations":
                args["patient_id"] = user_id
                args.pop("doctor_id", None)
                args.pop("clinic_id", None)
            elif fn_name == "get_patient_lab_results":
                try:
                    profile = await api_client.get_patient_profile_by_user_id(user_id)
                    args["patient_id"] = profile.get("id", user_id) if isinstance(profile, dict) else user_id
                except Exception:
                    args["patient_id"] = user_id
            elif fn_name == "get_patient_details":
                args["user_id"] = user_id

        # --- Clinic name -> ID resolution ---
        if fn_name in ("get_clinic_queue", "get_clinic_details", "get_clinic_doctors"):
            raw = str(args.get("clinic_id", "") or args.pop("clinic_name", ""))
            if not raw or raw.lower() == "none":
                if role_lower == "doctor":
                    try:
                        profile = await api_client.get_doctor_profile_by_user_id(user_id)
                        doc_id = profile.get("id") if isinstance(profile, dict) else None
                        if doc_id:
                            all_cd = await api_client.get_all_clinic_doctors()
                            if isinstance(all_cd, list):
                                my_clinic_ids = [(cd.get("clinic") or {}).get("id") for cd in all_cd if cd.get("doctorRefId") == doc_id]
                                if my_clinic_ids:
                                    args["clinic_id"] = str(my_clinic_ids[0])
                                else:
                                    return json.dumps({"error": "You are not assigned to any clinics."})
                    except Exception as e:
                        print(f"Error auto-detecting doctor clinic: {e}")
            elif not raw.isdigit():
                resolved = await _resolve_clinic_id(raw)
                if not resolved:
                    return json.dumps({"error": f"No clinic found matching '{raw}'. Use get_all_clinics to see available clinics."})
                print(f"[Clinic Resolve] '{raw}' -> ID {resolved}")
                args["clinic_id"] = resolved

        # --- Doctor name -> ID resolution for create_clinic ---
        if fn_name == "create_clinic":
            doctor_names = args.pop("doctorNames", [])
            if doctor_names:
                all_doctors = await api_client.get_all_doctors()
                if isinstance(all_doctors, list):
                    doctor_ids = args.get("doctorIds", [])
                    for name in doctor_names:
                        name_lower = name.lower()
                        for doc in all_doctors:
                            doc_name = (doc.get("name") or doc.get("doctorName", "")).lower()
                            if doc_name and (name_lower in doc_name or doc_name in name_lower):
                                doctor_ids.append(doc.get("id"))
                                break
                    args["doctorIds"] = list(set(doctor_ids))

        # --- Dispatch ---
        result = None

        if fn_name == "get_all_patients":
            result = await api_client.get_all_patients()
        elif fn_name == "get_patient_details":
            result = await api_client.get_patient_profile_by_user_id(args["user_id"])
        elif fn_name == "get_all_doctors":
            result = await api_client.get_all_doctors()
        elif fn_name == "get_all_clinics":
            result = await api_client.get_all_clinics()
            if role_lower == "doctor" and isinstance(result, list):
                try:
                    profile = await api_client.get_doctor_profile_by_user_id(user_id)
                    doc_id = profile.get("id") if isinstance(profile, dict) else None
                    if doc_id:
                        all_cd = await api_client.get_all_clinic_doctors()
                        if isinstance(all_cd, list):
                            my_clinic_ids = {(cd.get("clinic") or {}).get("id") for cd in all_cd if cd.get("doctorRefId") == doc_id}
                            result = [c for c in result if c.get("id") in my_clinic_ids]
                except Exception as e:
                    print(f"Error filtering clinics for doctor: {e}")
        elif fn_name == "get_clinic_details":
            result = await api_client.get_clinic(int(args["clinic_id"]))
        elif fn_name == "get_clinic_doctors":
            result = await api_client.get_clinic_doctors(int(args["clinic_id"]))
        elif fn_name == "get_clinic_queue":
            result = await api_client.get_clinic_queue(str(args["clinic_id"]))
            # Annotate patient's own tokens
            if role_lower == "patient" and isinstance(result, list):
                try:
                    profile = await api_client.get_patient_profile_by_user_id(user_id)
                    pid = profile.get("id") if isinstance(profile, dict) else None
                    my_tokens = []
                    if pid:
                        for tok in result:
                            if tok.get("patientId") and int(tok["patientId"]) == int(pid):
                                tok["_is_current_user"] = True
                                my_tokens.append({
                                    "token_number": tok.get("tokenNumber"),
                                    "position": tok.get("position"),
                                    "status": tok.get("status"),
                                })
                    result = {
                        "queue": result,
                        "_current_user_tokens": my_tokens or "You have no tokens in this queue.",
                    }
                except Exception:
                    pass
        elif fn_name == "get_consultations":
            result = await api_client.get_consultations(
                patient_id=args.get("patient_id"),
                doctor_id=args.get("doctor_id"),
                clinic_id=args.get("clinic_id"),
                status=args.get("status"),
            )
        elif fn_name == "get_consultation":
            result = await api_client.get_consultation(args["consultation_id"])
        elif fn_name == "get_consultation_with_tests":
            result = await api_client.get_consultation_with_tests(args["consultation_id"])
        elif fn_name == "get_lab_tests":
            result = await api_client.get_lab_tests(
                status=args.get("status"),
                technician_id=args.get("technician_id"),
            )
        elif fn_name == "get_lab_tests_by_consultation":
            result = await api_client.get_lab_tests_by_consultation(args["consultation_id"])
        elif fn_name == "get_patient_lab_results":
            result = await api_client.get_test_results_by_patient(args["patient_id"])
        elif fn_name == "get_test_result":
            result = await api_client.get_test_result(args["test_result_id"])
        elif fn_name == "get_test_result_by_lab_test":
            result = await api_client.get_test_result_by_lab_test(args["lab_test_id"])
        elif fn_name == "get_all_test_results":
            result = await api_client.get_all_test_results()
        elif fn_name == "get_queue_token":
            result = await api_client.get_queue_token(args["token_id"])
        elif fn_name == "get_all_technicians":
            result = await api_client.get_all_technicians()
        elif fn_name == "get_doctor_profile":
            result = await api_client.get_doctor_profile(args["doctor_id"])
        elif fn_name == "get_my_profile":
            if role_lower == "doctor":
                result = await api_client.get_doctor_profile_by_user_id(user_id)
            elif role_lower == "patient":
                result = await api_client.get_patient_profile_by_user_id(user_id)
            elif role_lower == "admin":
                try:
                    result = await api_client.get_admin_profile_by_user_id(user_id)
                except Exception:
                    result = await api_client.get_user(user_id)
        elif fn_name == "get_all_users":
            result = await api_client.get_all_users()
        elif fn_name == "create_clinic":
            result = await api_client.create_clinic(args)
        elif fn_name == "update_clinic":
            result = await api_client.update_clinic(args["clinic_id"], args.get("data", {}))
        elif fn_name == "delete_clinic":
            result = await api_client.delete_clinic(args["clinic_id"])
        elif fn_name == "create_consultation":
            result = await api_client.create_consultation(args)
        elif fn_name == "update_consultation":
            cid = args.pop("consultation_id")
            result = await api_client.update_consultation(cid, args)
        elif fn_name == "complete_consultation":
            result = await api_client.complete_consultation(args["consultation_id"])
        elif fn_name == "cancel_consultation":
            result = await api_client.cancel_consultation(args["consultation_id"])
        elif fn_name == "update_user":
            result = await api_client.update_user(args["user_id"], args.get("data", {}))

        else:
            return json.dumps({"error": f"Unknown tool: {fn_name}"})

        # Annotate empty/none results
        if result is None:
            return json.dumps({"data": None, "message": "No data found."})
        if isinstance(result, list) and len(result) == 0:
            return json.dumps({"data": [], "message": f"No records found for {fn_name}."})

        # Truncate large results aggressively to stay under ITPM limits on Groq free tier
        result_str = json.dumps(result, default=str)
        MAX_RESULT_CHARS = 8000  # Keep payloads small to avoid rate limits
        if len(result_str) > MAX_RESULT_CHARS:
            if isinstance(result, list):
                # Keep trimming until it fits
                limit = min(30, len(result))
                while limit > 1:
                    trimmed_str = json.dumps(
                        {"data": result[:limit], "_note": f"Showing {limit} of {len(result)} records."},
                        default=str,
                    )
                    if len(trimmed_str) <= MAX_RESULT_CHARS:
                        result_str = trimmed_str
                        break
                    limit = limit // 2
            else:
                result_str = result_str[:MAX_RESULT_CHARS] + '..."truncated"}'
        return result_str

    except Exception as e:
        traceback.print_exc()
        return json.dumps({"error": f"Tool {fn_name} failed: {str(e)}"})


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------
def _build_system_prompt(role: str, user_id: int) -> str:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    base = (
        f"You are Arogya AI, a healthcare assistant for the Arogya mobile clinic management system in Sri Lanka. "
        f"You are friendly, professional, and concise. Current date/time: {today}.\n\n"
        f"CRITICAL RULES:\n"
        f"- NEVER invent or fabricate data. Only use data returned by tool calls.\n"
        f"- NEVER narrate your tool usage (do not say 'Let me call get_all_clinics', just call it).\n"
        f"- If a tool returns empty data, say so clearly.\n"
        f"- Always use tools when live data is needed. Do not guess.\n"
        f"- When a user requests an action (like creating a clinic or scheduling a consultation), check the required parameters for the corresponding tool. If any are missing, ask the user to provide them BEFORE calling the tool. Do not invent missing values.\n"
    )
    role_lower = role.lower()
    if role_lower == "admin":
        return base + (
            f"\nThe current user is an ADMIN (user ID: {user_id}). "
            "Admins have full access: all patients, doctors, clinics, queues, consultations, lab results, and users."
        )
    elif role_lower == "doctor":
        return base + (
            f"\nThe current user is a DOCTOR (user ID: {user_id}). "
            "Doctors can view patient details, their own consultations (doctor_id={user_id}), "
            "clinic queues, and lab results. They cannot view other doctors private data.\n"
            "When asked about your own consultations, use doctor_id={user_id} in get_consultations."
        ).format(user_id=user_id)
    elif role_lower == "patient":
        return base + (
            f"\nThe current user is a PATIENT (user ID: {user_id}). "
            "Patients can ONLY see their own data. "
            "When fetching consultations or lab results, the system will automatically scope to this patient. "
            "Patients can browse available clinics. If they ask for nearby or upcoming clinics, ALWAYS use the `get_all_clinics` tool, and then manually filter the results based on their location and the current date to provide the most relevant upcoming options."
        )
    return base + f"\nThe current user has role '{role}' (user ID: {user_id})."


# ---------------------------------------------------------------------------
# Tool-calling loop
# ---------------------------------------------------------------------------
async def _run_tool_loop(full_messages: list[dict], tools: list[dict], role: str, user_id: int) -> str:
    retry_no_tool = False
    for round_num in range(MAX_TOOL_ROUNDS):
        try:
            kwargs = {
                "messages": full_messages,
                "temperature": 0,
                "parallel_tool_calls": False,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = await _llm_call(**kwargs)
        except Exception as e:
            print(f"[Tool Loop Error] {e}")
            return "I am having trouble connecting to the AI service. Please try again in a moment."

        choice = response.choices[0]
        msg = choice.message

        # Check for tool calls
        if choice.finish_reason == "tool_calls" or (msg.tool_calls and len(msg.tool_calls) > 0):
            # Build cleaned tool_calls list for history
            cleaned_calls = []
            for tc in msg.tool_calls:
                try:
                    fn_args = json.loads(tc.function.arguments or "{}")
                    if not isinstance(fn_args, dict):
                        fn_args = {}
                    # Remove null values
                    fn_args = {k: v for k, v in fn_args.items() if v is not None}
                except (json.JSONDecodeError, TypeError):
                    fn_args = {}
                cleaned_calls.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": json.dumps(fn_args)},
                })

            # Do NOT include content key when tool_calls present - some providers reject empty string
            assistant_msg = {"role": "assistant", "tool_calls": cleaned_calls}
            if msg.content:  # only add content if non-empty
                assistant_msg["content"] = msg.content
            full_messages.append(assistant_msg)

            # Execute each tool call
            for tc_cleaned, tc_original in zip(cleaned_calls, msg.tool_calls):
                fn_name = tc_original.function.name
                try:
                    fn_args = json.loads(tc_cleaned["function"]["arguments"])
                except Exception:
                    fn_args = {}
                print(f"[Tool Call] {fn_name}({fn_args})")
                tool_result = await _execute_tool(fn_name, fn_args, role, user_id)
                print(f"[Tool Result] {fn_name} -> {len(tool_result)} chars")
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tc_cleaned["id"],
                    "content": tool_result,
                })
            continue  # next round

        # No tool calls - final response
        reply = (msg.content or "").strip()

        # Model returned nothing - this can happen on some providers; retry once
        if not reply:
            print(f"[Warn] Empty reply on round {round_num}, retrying...")
            full_messages.append({"role": "user", "content": "Please provide a response."})
            continue

        # Detect fake tool call in text (model hallucinating tool calls as text)
        if _is_fake_tool_call(reply) and not retry_no_tool:
            retry_no_tool = True
            full_messages.append({"role": "assistant", "content": reply})
            full_messages.append({
                "role": "user",
                "content": (
                    "Please use the proper tool_calls mechanism to fetch data. "
                    "Do not write function calls as text."
                ),
            })
            continue

        return _clean_response(reply) or "I could not generate a response."

    return "I reached the maximum number of processing steps. Please try rephrasing your question."


# ---------------------------------------------------------------------------
# Simple reply (no tools)
# ---------------------------------------------------------------------------
async def _run_simple_reply(full_messages: list[dict], sanitize: bool = False) -> str:
    try:
        resp = await _llm_call(messages=full_messages, temperature=0.2)
        content = (resp.choices[0].message.content or "").strip()
        return _clean_response(content) or "I could not generate a response."
    except Exception as e:
        print(f"[Simple Reply Error] {e}")
        return "I am having trouble connecting to the AI service. Please try again in a moment."


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
import system1_router

async def chat(messages: list[dict], role: str, user_id: int) -> str:
    """
    Main chat function. Routes to tool loop or simple reply based on intent.
    """
    system_prompt = _build_system_prompt(role, user_id)
    tools = get_tools_for_role(role)
    full_messages = [{"role": "system", "content": system_prompt}] + list(messages)

    intent = await system1_router.fast_intent_classification(messages)
    print(f"[System 1 Router] intent={intent}")

    if intent == "tool":
        selected_tool_name = await system1_router.fast_tool_selection(messages, tools)
        print(f"[System 1 Router] selected tool: {selected_tool_name}")
        
        if selected_tool_name != "unknown":
            # Pass ONLY the selected tool to the generative LLM
            tools = [t for t in tools if t["function"]["name"] == selected_tool_name]
            
            # Optimization: If the selected tool has NO parameters, execute it immediately!
            if tools:
                selected_tool = tools[0]
                params = selected_tool["function"].get("parameters", {}).get("properties", {})
                if not params:
                    print(f"[System 1 Router] Tool {selected_tool_name} requires no args, executing directly!")
                    tool_result = await _execute_tool(selected_tool_name, {}, role, user_id)
                    full_messages.append({
                        "role": "user",
                        "content": f"System retrieved data: {tool_result}\n\nPlease summarize this clearly for me.",
                    })
                    return await _run_simple_reply(full_messages)

        return await _run_tool_loop(full_messages, tools, role, user_id)

    if intent == "health" and role.lower() == "patient":
        latest_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if latest_msg:
            import os
            import asyncio
            from gradio_client import Client
            
            def _call_gradio(msg):
                hf_token = os.getenv("HF_API_KEY")
                client = Client("Thanu10/Arogya-Medical-Chat", hf_token=hf_token)
                return client.predict(message=msg, api_name="/generate_response")

            try:
                print(f"[Gradio] Forwarding to Arogya-Medical-Chat: {latest_msg[:50]}...")
                gradio_response = await asyncio.to_thread(_call_gradio, latest_msg)
                if gradio_response:
                    return _clean_response(str(gradio_response))
            except Exception as e:
                print(f"[Gradio Error] {e}")
                # Fall through to simple reply below if Gradio fails

    return await _run_simple_reply(full_messages, sanitize=(intent == "health"))
