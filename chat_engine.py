"""
Core chat engine: manages conversations with Grok, executes tool calls,
enforces role-based access, and supports analytical queries.
"""

import json
import traceback
from datetime import datetime
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
        f"15. For small talk or greetings, respond naturally without calling any tools.\n"
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
            "NEVER fetch or reveal other patients' data."
        )
    return base


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
            if function_name == "get_consultations":
                # Get patient profile first to get the correct ID
                try:
                    profile = await api_client.get_patient_profile_by_user_id(user_id)
                    if profile and isinstance(profile, dict) and profile.get("id"):
                        arguments["patient_id"] = profile["id"]
                    else:
                        arguments["patient_id"] = user_id  # fallback
                except Exception:
                    arguments["patient_id"] = user_id  # fallback
                arguments.pop("doctor_id", None)
                arguments.pop("clinic_id", None)
            elif function_name == "get_patient_lab_results":
                # Get patient profile ID for lab results
                try:
                    profile = await api_client.get_patient_profile_by_user_id(user_id)
                    if profile and isinstance(profile, dict) and profile.get("id"):
                        arguments["patient_id"] = profile["id"]
                    else:
                        arguments["patient_id"] = user_id  # fallback
                except Exception:
                    arguments["patient_id"] = user_id  # fallback
            elif function_name == "get_patient_details":
                arguments["user_id"] = user_id
            elif function_name in ("get_all_patients", "get_all_doctors", "get_all_users"):
                return json.dumps({"error": "Access denied. Patients cannot view other users' data."})

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
            result = await api_client.get_clinic(arguments["clinic_id"])

        elif function_name == "get_clinic_doctors":
            result = await api_client.get_clinic_doctors(arguments["clinic_id"])

        elif function_name == "get_clinic_queue":
            result = await api_client.get_clinic_queue(arguments["clinic_id"])

        elif function_name == "get_consultations":
            result = await api_client.get_consultations(
                patient_id=arguments.get("patient_id"),
                doctor_id=arguments.get("doctor_id"),
                clinic_id=arguments.get("clinic_id"),
                status=arguments.get("status"),
            )

        elif function_name == "get_consultation_with_tests":
            result = await api_client.get_consultation_with_tests(arguments["consultation_id"])

        elif function_name == "get_lab_tests":
            result = await api_client.get_lab_tests(
                status=arguments.get("status"),
                technician_id=arguments.get("technician_id"),
            )

        elif function_name == "get_patient_lab_results":
            result = await api_client.get_test_results_by_patient(arguments["patient_id"])

        elif function_name == "get_my_profile":
            if role.lower() == "doctor":
                result = await api_client.get_doctor_profile_by_user_id(user_id)
            elif role.lower() == "patient":
                result = await api_client.get_patient_profile_by_user_id(user_id)
            elif role.lower() == "admin":
                try:
                    result = await api_client.get_all_admins()
                    # find the admin whose user.id matches
                    if isinstance(result, list):
                        match = [a for a in result if a.get("user", {}).get("id") == user_id]
                        result = match[0] if match else result
                except Exception:
                    result = await api_client.get_user(user_id)

        elif function_name == "get_all_users":
            result = await api_client.get_all_users()

        else:
            return json.dumps({"error": f"Unknown tool: {function_name}"})

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
                "content": choice.message.content,
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
        return choice.message.content or "I'm sorry, I couldn't generate a response. Please try again."

    return "I've reached the maximum number of processing steps. Please try simplifying your question."
