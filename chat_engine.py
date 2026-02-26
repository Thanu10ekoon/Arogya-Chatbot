"""
Core chat engine: manages conversations with Grok, executes tool calls,
enforces role-based access, and supports analytical queries.
"""

import json
import traceback
from datetime import datetime
from difflib import SequenceMatcher
from openai import AsyncOpenAI

import api_client
from config import GROQ_API_KEY, GROQ_MODEL
from tools import get_tools_for_role

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

MAX_TOOL_ROUNDS = 6  # prevent infinite loops


def _build_system_prompt(role: str, user_id: int) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    base = (
        f"You are Arogya AI, a helpful healthcare assistant for the Arogya mobile clinic management system in Sri Lanka. "
        f"You are friendly, professional, and concise. You can answer general health questions, "
        f"help users navigate the system, and fetch real-time data from the backend when asked.\n\n"
        f"CURRENT DATE AND TIME: {current_datetime} (Today is {today})\n\n"
        f"CRITICAL FUNCTION CALLING RULES:\n"
        f"1. When you need to fetch data, ONLY call the function - do NOT generate or invent the response data.\n"
        f"2. After calling a function, WAIT for the result. Do NOT continue writing or make up example data.\n"
        f"3. NEVER include sample data, placeholders, or made-up responses in your function calls.\n"
        f"4. Once you receive the tool result, THEN format and present it to the user.\n\n"
        f"DATE-BASED ANALYSIS RULES:\n"
        f"5. When asked about 'completed' events, compare the scheduled_date with today's date ({today}).\n"
        f"6. An event/clinic is considered COMPLETED if its scheduled_date is BEFORE today ({today}), regardless of its status field.\n"
        f"7. An event/clinic is considered UPCOMING if its scheduled_date is ON or AFTER today ({today}).\n"
        f"8. When analyzing dates, be precise. For queries like 'December 2025', only count records with dates in that specific month/year.\n\n"
        f"DATA HANDLING RULES:\n"
        f"9. Do NOT make up patient names, IDs, clinic names, dates, or any medical data.\n"
        f"10. Present data in a clear, readable format (use bullet points or numbered lists when appropriate).\n"
        f"11. For analytical questions (trends, predictions, comparisons), fetch the relevant data first, then analyze it thoroughly.\n"
        f"12. If a backend service returns an error, inform the user clearly that the service is unavailable. Do NOT expose raw error details.\n"
        f"13. Keep responses concise but complete.\n"
        f"14. Never expose raw JSON to the user; always format it nicely.\n"
        f"15. For small talk, greetings, or general questions about Arogya (what it is, how it works, its features, etc.), respond naturally from your own knowledge WITHOUT calling any tools. "
        f"You already know that Arogya is a mobile clinic management system for Sri Lanka that handles clinics, patient records, consultations, lab tests, doctor management, and queue management.\n"
        f"16. ONLY call get_my_profile when the user EXPLICITLY asks to see their own profile, personal details, or account information. Do NOT call it for general questions.\n\n"
        f"RESPONSE STYLE RULES:\n"
        f"17. NEVER show your internal reasoning, intermediate steps, or thinking process to the user.\n"
        f"18. NEVER display raw JSON, tool call details, clinic IDs, or API results in your response.\n"
        f"19. NEVER say phrases like 'I'm calling...', 'Let me fetch...', 'I need to first get...', 'Calling X...', 'I will use...', 'I'm fetching...' etc.\n"
        f"20. ONLY present the FINAL, user-friendly answer AFTER you have the data. Skip ALL narration and go straight to the answer.\n\n"
        f"CLINIC NAME RESOLUTION RULES:\n"
        f"21. Users refer to clinics by NAME (e.g., 'Kalutara clinic', 'Kandy Mobile Clinic'), NOT by numeric ID.\n"
        f"22. When a user asks about a specific clinic by name, call get_clinic_queue/get_clinic_details/get_clinic_doctors directly with the clinic name — the system will automatically resolve it to the correct numeric ID.\n"
        f"23. If no clinic matches the name, tell the user the clinic was not found and list available clinics.\n"
    )

    if role.lower() == "admin":
        return base + (
            f"\nThe current user is an ADMIN (user ID: {user_id}). "
            "Admins have full access to all patient records, all clinics, all consultations, all doctors, and all analytics. "
            "When asked analytical questions (e.g., 'Will this area have more diabetic patients next year?'), "
            "fetch all patient data, examine chronic diseases and addresses, and provide a data-driven analysis with reasoning. "
            "You can also provide system-wide statistics and summaries."
        )
    elif role.lower() == "doctor":
        return base + (
            f"\nThe current user is a DOCTOR (user ID: {user_id}). "
            "Doctors can view their own profile, see patient details, view consultations (their own and their patients'), "
            "view clinic information, check queues, and see lab test results. "
            "When fetching your own consultations, use doctor_id={user_id}."
        )
    elif role.lower() == "patient":
        return base + (
            f"\nThe current user is a PATIENT (user ID: {user_id}). "
            "CRITICAL: Patients can ONLY access their OWN data. "
            "The backend will automatically filter consultations and lab results to show only your data, so you can call these functions without specifying IDs. "
            "Patients can also browse available clinics. "
            "NEVER fetch or reveal other patients' data.\n\n"
            "QUEUE POSITION RULES:\n"
            "When a patient asks about their queue position, call get_clinic_queue. "
            "The result will contain a '_current_user_tokens' field that shows ONLY the tokens belonging to this patient. "
            "Use THAT data to report the patient's position accurately. "
            "Do NOT guess or count manually — ONLY use the '_current_user_tokens' data."
        )
    return base


# ── Clinic name → ID fuzzy resolver ─────────────────────────────────────────

async def _resolve_clinic_id(name: str) -> str | None:
    """
    Fuzzy-match a user-provided clinic name to a numeric clinic ID.
    Returns the ID as a string, or None if no match found.
    """
    clinics = await api_client.get_all_clinics()
    if not isinstance(clinics, list) or not clinics:
        return None

    name_lower = name.lower().strip()

    # 1. Try exact match first
    for c in clinics:
        if c.get("clinicName", "").lower() == name_lower:
            return str(c["id"])

    # 2. Try substring / contains match
    for c in clinics:
        clinic_name = c.get("clinicName", "").lower()
        if name_lower in clinic_name or clinic_name in name_lower:
            return str(c["id"])

    # 3. Fuzzy match using SequenceMatcher
    best_score = 0.0
    best_id = None
    for c in clinics:
        clinic_name = c.get("clinicName", "").lower()
        score = SequenceMatcher(None, name_lower, clinic_name).ratio()
        # Also check against parts (e.g., "kalutara" vs "Kalutara Mobile Clinic")
        for word in name_lower.split():
            word_score = SequenceMatcher(None, word, clinic_name.split()[0] if clinic_name.split() else "").ratio()
            score = max(score, word_score)
        if score > best_score:
            best_score = score
            best_id = str(c["id"])

    if best_score >= 0.6:
        return best_id

    return None


async def _execute_tool(
    function_name: str,
    arguments: dict,
    role: str,
    user_id: int,
) -> str:
    """Execute a tool call and return the result as a JSON string."""

    try:
        # ── Role-based access enforcement ────────────────────────────────
        if role.lower() == "patient":
            # Force patient to only see own data
            # For consultations, use patient_profile_id not user_id
            if function_name in ("get_consultations", "get_patient_lab_results"):
                # Get patient profile first to get the correct ID
                try:
                    profile = await api_client.get_patient_profile_by_user_id(user_id)
                    if profile and isinstance(profile, dict) and profile.get("id"):
                        arguments["patient_id"] = profile["id"]
                    else:
                        arguments["patient_id"] = user_id  # fallback
                except Exception:
                    arguments["patient_id"] = user_id  # fallback
                if function_name == "get_consultations":
                    arguments.pop("doctor_id", None)
                    arguments.pop("clinic_id", None)
            elif function_name == "get_patient_details":
                arguments["user_id"] = user_id
            elif function_name in ("get_all_patients", "get_all_doctors", "get_all_users",
                                   "get_all_technicians", "get_all_test_results"):
                return json.dumps({"error": "Access denied. Patients cannot view other users' data."})

        # ── Clinic name → ID resolution ──────────────────────────────────
        # If get_clinic_queue / get_clinic_details / get_clinic_doctors was
        # called with a non-numeric clinic_id (i.e. a name), resolve it.
        if function_name in ("get_clinic_queue", "get_clinic_details", "get_clinic_doctors"):
            raw_id = str(arguments.get("clinic_id", ""))
            # Also grab any stray clinic_name the LLM might have invented
            raw_name = arguments.pop("clinic_name", None)
            lookup = raw_name or raw_id

            if not lookup.isdigit():
                resolved = await _resolve_clinic_id(lookup)
                if resolved is None:
                    return json.dumps({
                        "error": f"No clinic found matching '{lookup}'. "
                                 "Call get_all_clinics to see the full list."
                    })
                arguments["clinic_id"] = resolved
                print(f"[Clinic Resolve] '{lookup}' → ID {resolved}")

        # ── Dispatch to API client ───────────────────────────────────────
        result = None

        if function_name == "get_all_patients":
            result = await api_client.get_all_patients()

        elif function_name == "get_patient_details":
            result = await api_client.get_patient_profile_by_user_id(arguments["user_id"])

        elif function_name == "get_all_doctors":
            result = await api_client.get_all_doctors()

        elif function_name == "get_all_clinics":
            result = await api_client.get_all_clinics()

        elif function_name == "get_clinic_details":
            result = await api_client.get_clinic(int(arguments["clinic_id"]))

        elif function_name == "get_clinic_doctors":
            result = await api_client.get_clinic_doctors(int(arguments["clinic_id"]))

        elif function_name == "get_clinic_queue":
            result = await api_client.get_clinic_queue(str(arguments["clinic_id"]))
            # Annotate which tokens belong to the current user so the LLM
            # can accurately report "your position" instead of guessing.
            if role.lower() == "patient" and isinstance(result, list):
                try:
                    profile = await api_client.get_patient_profile_by_user_id(user_id)
                    patient_profile_id = profile.get("id") if isinstance(profile, dict) else None
                    if patient_profile_id is not None:
                        my_tokens = []
                        for token in result:
                            pid = token.get("patientId") or token.get("patient_id")
                            if pid is not None and int(pid) == int(patient_profile_id):
                                token["_is_current_user"] = True
                                my_tokens.append({
                                    "token_number": token.get("tokenNumber"),
                                    "position": token.get("position"),
                                    "status": token.get("status"),
                                })
                        result = {
                            "queue": result,
                            "_current_user_tokens": my_tokens if my_tokens else "You do not have any tokens in this clinic's queue.",
                            "_note": "Tokens marked with _is_current_user=True belong to the currently logged-in patient. Use these to report their queue position accurately."
                        }
                except Exception:
                    pass  # fall through with unmodified result

        elif function_name == "get_consultations":
            result = await api_client.get_consultations(
                patient_id=arguments.get("patient_id"),
                doctor_id=arguments.get("doctor_id"),
                clinic_id=arguments.get("clinic_id"),
                status=arguments.get("status"),
            )

        elif function_name == "get_consultation":
            result = await api_client.get_consultation(arguments["consultation_id"])

        elif function_name == "get_consultation_with_tests":
            result = await api_client.get_consultation_with_tests(arguments["consultation_id"])

        elif function_name == "get_lab_tests":
            result = await api_client.get_lab_tests(
                status=arguments.get("status"),
                technician_id=arguments.get("technician_id"),
            )

        elif function_name == "get_lab_tests_by_consultation":
            result = await api_client.get_lab_tests_by_consultation(arguments["consultation_id"])

        elif function_name == "get_patient_lab_results":
            result = await api_client.get_test_results_by_patient(arguments["patient_id"])

        elif function_name == "get_test_result":
            result = await api_client.get_test_result(arguments["test_result_id"])

        elif function_name == "get_test_result_by_lab_test":
            result = await api_client.get_test_result_by_lab_test(arguments["lab_test_id"])

        elif function_name == "get_all_test_results":
            result = await api_client.get_all_test_results()

        elif function_name == "get_queue_token":
            result = await api_client.get_queue_token(arguments["token_id"])

        elif function_name == "get_all_technicians":
            result = await api_client.get_all_technicians()

        elif function_name == "get_doctor_profile":
            result = await api_client.get_doctor_profile(arguments["doctor_id"])

        elif function_name == "get_my_profile":
            if role.lower() == "doctor":
                result = await api_client.get_doctor_profile_by_user_id(user_id)
            elif role.lower() == "patient":
                result = await api_client.get_patient_profile_by_user_id(user_id)
            elif role.lower() == "admin":
                try:
                    result = await api_client.get_admin_profile_by_user_id(user_id)
                except Exception:
                    result = await api_client.get_user(user_id)

        elif function_name == "get_all_users":
            result = await api_client.get_all_users()

        else:
            return json.dumps({"error": f"Unknown tool: {function_name}"})

        # ── Annotate empty results so LLM doesn't confuse them with errors ──
        if result is None:
            return json.dumps({"data": None, "message": "No data found. The record may not exist."})
        if isinstance(result, list) and len(result) == 0:
            return json.dumps({"data": [], "message": f"No records found for {function_name}. This is not an error — there is simply no data matching the query."})

        # Truncate very large results to avoid token limits
        result_str = json.dumps(result, default=str)
        if len(result_str) > 30000:
            # Summarize: keep first 60 items if it's a list
            if isinstance(result, list) and len(result) > 60:
                truncated = result[:60]
                result_str = json.dumps(
                    {"data": truncated, "_note": f"Showing 60 of {len(result)} records. Analyze based on this sample."},
                    default=str,
                )
            else:
                result_str = result_str[:30000] + '..."truncated"}'

        return result_str

    except Exception as e:
        traceback.print_exc()
        return json.dumps({"error": f"Failed to execute {function_name}: {str(e)}"})


import re

# Patterns that indicate narration / thinking leaking into the final response
_NARRATION_PATTERNS = [
    re.compile(r"^.*?I'm calling\b.*?\.\s*\n?", re.IGNORECASE),
    re.compile(r"^.*?I will call\b.*?\.\s*\n?", re.IGNORECASE),
    re.compile(r"^.*?Let me (?:fetch|get|check|call|look)\b.*?\.\s*\n?", re.IGNORECASE),
    re.compile(r"^.*?I need to first\b.*?\.\s*\n?", re.IGNORECASE),
    re.compile(r"^.*?Calling \w+.*?\.\s*\n?", re.IGNORECASE),
    re.compile(r"^.*?I'm fetching\b.*?\.\s*\n?", re.IGNORECASE),
    re.compile(r"^.*?I will use\b.*?\.\s*\n?", re.IGNORECASE),
    re.compile(r"^.*?I'll (?:fetch|get|check|call|look)\b.*?\.\s*\n?", re.IGNORECASE),
]


def _clean_response(text: str) -> str:
    """Strip narration / thinking prefixes from the LLM's final response."""
    cleaned = text.strip()
    for pattern in _NARRATION_PATTERNS:
        cleaned = pattern.sub("", cleaned, count=1).strip()
    return cleaned or text


async def chat(
    messages: list[dict],
    role: str,
    user_id: int,
) -> str:
    """
    Run a multi-turn chat with Grok, automatically handling tool calls.
    Returns the final assistant text response.
    """

    system_prompt = _build_system_prompt(role, user_id)
    tools = get_tools_for_role(role)

    # Build the full message list with system prompt
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    for _round in range(MAX_TOOL_ROUNDS):
        kwargs = {
            "model": GROQ_MODEL,
            "messages": full_messages,
            "temperature": 0.1,  # Lower temperature for more consistent function calling
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
            kwargs["parallel_tool_calls"] = False  # Force sequential tool calls

        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as e:
            error_msg = str(e)
            print(f"[Chat Error] {error_msg}")
            # If tool calling failed, try without tools as fallback
            if "tool" in error_msg.lower() or "function" in error_msg.lower():
                try:
                    fallback_response = await client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=full_messages,
                        temperature=0.1,
                    )
                    return fallback_response.choices[0].message.content or "I apologize, but I encountered a technical issue. Please try rephrasing your question."
                except Exception:
                    pass
            return f"I encountered an error while processing your request. Please try again or rephrase your question."
        
        choice = response.choices[0]

        # If the model wants to call tools
        if choice.finish_reason == "tool_calls" or (choice.message.tool_calls and len(choice.message.tool_calls) > 0):
            # Add the assistant message with tool calls (only include supported fields)
            # Filter out null values from arguments to satisfy Groq's strict validation
            tool_calls_cleaned = []
            for tc in choice.message.tool_calls:
                try:
                    args_dict = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    if args_dict is None:
                        args_dict = {}
                    # Remove null values - Groq rejects null for typed optional params
                    args_dict_filtered = {k: v for k, v in args_dict.items() if v is not None}
                    args_str = json.dumps(args_dict_filtered)
                except (json.JSONDecodeError, AttributeError, TypeError):
                    args_str = tc.function.arguments or "{}"
                
                tool_calls_cleaned.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": args_str,
                    }
                })
            
            assistant_msg = {
                "role": "assistant",
                "content": None,  # Strip intermediate thinking text — only the final response should have content
                "tool_calls": tool_calls_cleaned
            }
            full_messages.append(assistant_msg)

            # Execute each tool call
            for tool_call in choice.message.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    if fn_args is None:
                        fn_args = {}
                    # Remove null values before execution too
                    fn_args = {k: v for k, v in fn_args.items() if v is not None}
                except (json.JSONDecodeError, TypeError):
                    fn_args = {}

                print(f"[Tool Call] {fn_name}({fn_args})")
                tool_result = await _execute_tool(fn_name, fn_args, role, user_id)
                print(f"[Tool Result] {fn_name} → {len(tool_result)} chars")

                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                })

            # Continue the loop to get the next response
            continue

        # No tool calls — return the text response
        reply = choice.message.content or "I'm sorry, I couldn't generate a response. Please try again."
        return _clean_response(reply)

    return "I've reached the maximum number of processing steps. Please try simplifying your question."
