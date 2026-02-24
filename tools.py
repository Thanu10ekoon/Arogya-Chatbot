"""
Tool definitions for Grok function-calling, filtered by user role.
Each tool maps to a backend API call in api_client.py.
"""

# ────────────────────────────────────────────────────────────────────────────
# Tool schemas (OpenAI-compatible function-calling format)
# ────────────────────────────────────────────────────────────────────────────

TOOL_GET_ALL_PATIENTS = {
    "type": "function",
    "function": {
        "name": "get_all_patients",
        "description": "Get a list of ALL patient profiles including their names, NIC, blood group, allergies, chronic diseases, address, gender, emergency contact, date of birth, and phone number. Use this for bulk analysis or when asked about patient statistics.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

TOOL_GET_PATIENT_DETAILS = {
    "type": "function",
    "function": {
        "name": "get_patient_details",
        "description": "Get a specific patient's profile details by their user ID. Returns first name, last name, NIC, blood group, allergies, chronic diseases, address, gender, date of birth, phone number, and emergency contact.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "The user ID of the patient"},
            },
            "required": ["user_id"],
        },
    },
}

TOOL_GET_ALL_DOCTORS = {
    "type": "function",
    "function": {
        "name": "get_all_doctors",
        "description": "Get a list of all doctor profiles including their names, specialization, qualification, experience, license number, and phone number.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

TOOL_GET_ALL_CLINICS = {
    "type": "function",
    "function": {
        "name": "get_all_clinics",
        "description": "Get a list of all clinics/mobile clinics including their names, province, district, location, scheduled date, scheduled time, and status.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

TOOL_GET_CLINIC_DETAILS = {
    "type": "function",
    "function": {
        "name": "get_clinic_details",
        "description": "Get details of a specific clinic by its ID, including its name, province, district, location, scheduled date and time, and status.",
        "parameters": {
            "type": "object",
            "properties": {
                "clinic_id": {"type": "integer", "description": "The clinic ID"},
            },
            "required": ["clinic_id"],
        },
    },
}

TOOL_GET_CLINIC_DOCTORS = {
    "type": "function",
    "function": {
        "name": "get_clinic_doctors",
        "description": "Get the list of doctors assigned to a specific clinic.",
        "parameters": {
            "type": "object",
            "properties": {
                "clinic_id": {"type": "integer", "description": "The clinic ID"},
            },
            "required": ["clinic_id"],
        },
    },
}

TOOL_GET_CLINIC_QUEUE = {
    "type": "function",
    "function": {
        "name": "get_clinic_queue",
        "description": "Get the current patient queue (tokens) for a specific clinic. Shows token numbers, positions, statuses (PENDING/SERVING/COMPLETED/CANCELLED), and patient IDs.",
        "parameters": {
            "type": "object",
            "properties": {
                "clinic_id": {"type": "string", "description": "The clinic ID as a string"},
            },
            "required": ["clinic_id"],
        },
    },
}

TOOL_GET_CONSULTATIONS = {
    "type": "function",
    "function": {
        "name": "get_consultations",
        "description": "Get consultations with optional filtering. Can filter by patient ID, doctor ID, clinic ID, or status (SCHEDULED/IN_PROGRESS/COMPLETED/CANCELLED). Returns chief complaint, present illness, past medical history, recommendations, session number, and timestamps.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "Filter by patient's user ID"},
                "doctor_id": {"type": "integer", "description": "Filter by doctor's user ID"},
                "clinic_id": {"type": "integer", "description": "Filter by clinic ID"},
                "status": {
                    "type": "string",
                    "description": "Filter by status",
                    "enum": ["SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"],
                },
            },
            "required": [],
        },
    },
}

TOOL_GET_CONSULTATION_WITH_TESTS = {
    "type": "function",
    "function": {
        "name": "get_consultation_with_tests",
        "description": "Get a specific consultation along with all its associated lab tests. Returns consultation details plus lab test names, descriptions, statuses, and results.",
        "parameters": {
            "type": "object",
            "properties": {
                "consultation_id": {"type": "integer", "description": "The consultation ID"},
            },
            "required": ["consultation_id"],
        },
    },
}

TOOL_GET_LAB_TESTS = {
    "type": "function",
    "function": {
        "name": "get_lab_tests",
        "description": "Get lab tests with optional filtering by status (PENDING/IN_PROGRESS/COMPLETED/CANCELLED) or technician ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"],
                },
                "technician_id": {"type": "integer", "description": "Filter by technician ID"},
            },
            "required": [],
        },
    },
}

TOOL_GET_PATIENT_LAB_RESULTS = {
    "type": "function",
    "function": {
        "name": "get_patient_lab_results",
        "description": "Get all lab/test results for a specific patient. Returns test result descriptions, technician notes, file names, and timestamps.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "The patient's profile ID (not user ID)"},
            },
            "required": ["patient_id"],
        },
    },
}

TOOL_GET_MY_PROFILE = {
    "type": "function",
    "function": {
        "name": "get_my_profile",
        "description": "Get the currently logged-in user's own profile details (name, NIC, blood group, allergies, chronic diseases, etc. for patients; specialization, qualification, etc. for doctors).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

TOOL_GET_ALL_USERS = {
    "type": "function",
    "function": {
        "name": "get_all_users",
        "description": "Get a list of all registered users including their usernames, emails, and roles (patient/doctor/admin/technician).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


# ────────────────────────────────────────────────────────────────────────────
# Role → tool mapping
# ────────────────────────────────────────────────────────────────────────────

ADMIN_TOOLS = [
    TOOL_GET_ALL_PATIENTS,
    TOOL_GET_PATIENT_DETAILS,
    TOOL_GET_ALL_DOCTORS,
    TOOL_GET_ALL_CLINICS,
    TOOL_GET_CLINIC_DETAILS,
    TOOL_GET_CLINIC_DOCTORS,
    TOOL_GET_CLINIC_QUEUE,
    TOOL_GET_CONSULTATIONS,
    TOOL_GET_CONSULTATION_WITH_TESTS,
    TOOL_GET_LAB_TESTS,
    TOOL_GET_PATIENT_LAB_RESULTS,
    TOOL_GET_MY_PROFILE,
    TOOL_GET_ALL_USERS,
]

DOCTOR_TOOLS = [
    TOOL_GET_MY_PROFILE,
    TOOL_GET_PATIENT_DETAILS,
    TOOL_GET_ALL_CLINICS,
    TOOL_GET_CLINIC_DETAILS,
    TOOL_GET_CLINIC_DOCTORS,
    TOOL_GET_CLINIC_QUEUE,
    TOOL_GET_CONSULTATIONS,
    TOOL_GET_CONSULTATION_WITH_TESTS,
    TOOL_GET_LAB_TESTS,
    TOOL_GET_PATIENT_LAB_RESULTS,
]

PATIENT_TOOLS = [
    TOOL_GET_MY_PROFILE,
    TOOL_GET_ALL_CLINICS,
    TOOL_GET_CLINIC_DETAILS,
    TOOL_GET_CLINIC_DOCTORS,
    TOOL_GET_CONSULTATIONS,       # will be scoped to own data by chat_engine
    TOOL_GET_PATIENT_LAB_RESULTS, # will be scoped to own data by chat_engine
]


def get_tools_for_role(role: str) -> list[dict]:
    role_lower = role.lower()
    if role_lower == "admin":
        return ADMIN_TOOLS
    elif role_lower == "doctor":
        return DOCTOR_TOOLS
    elif role_lower == "patient":
        return PATIENT_TOOLS
    return []
