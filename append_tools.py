
import json

extra_tools_code = '''

TOOL_CREATE_CLINIC = {
    "type": "function",
    "function": {
        "name": "create_clinic",
        "description": "Create a new clinic.",
        "parameters": {
            "type": "object",
            "properties": {
                "clinicName": {"type": "string"},
                "province": {"type": "string"},
                "district": {"type": "string"},
                "location": {"type": "string"},
                "scheduledDate": {"type": "string"},
                "scheduledTime": {"type": "string"},
                "status": {"type": "string"}
            },
            "required": ["clinicName", "province", "district", "scheduledDate"]
        }
    }
}

TOOL_UPDATE_CLINIC = {
    "type": "function",
    "function": {
        "name": "update_clinic",
        "description": "Update an existing clinic.",
        "parameters": {
            "type": "object",
            "properties": {
                "clinic_id": {"type": "integer"},
                "data": {"type": "object"}
            },
            "required": ["clinic_id", "data"]
        }
    }
}

TOOL_DELETE_CLINIC = {
    "type": "function",
    "function": {
        "name": "delete_clinic",
        "description": "Delete a clinic.",
        "parameters": {
            "type": "object",
            "properties": {
                "clinic_id": {"type": "integer"}
            },
            "required": ["clinic_id"]
        }
    }
}

TOOL_CREATE_CONSULTATION = {
    "type": "function",
    "function": {
        "name": "create_consultation",
        "description": "Create a consultation.",
        "parameters": {
            "type": "object",
            "properties": {
                "patientId": {"type": "integer"},
                "doctorId": {"type": "integer"},
                "clinicId": {"type": "integer"},
                "queueTokenId": {"type": "integer"}
            },
            "required": ["patientId", "doctorId", "clinicId"]
        }
    }
}

TOOL_UPDATE_CONSULTATION = {
    "type": "function",
    "function": {
        "name": "update_consultation",
        "description": "Update consultation details (like recommendations, past medical history).",
        "parameters": {
            "type": "object",
            "properties": {
                "consultation_id": {"type": "integer"},
                "chiefComplaint": {"type": "string"},
                "presentIllness": {"type": "string"},
                "pastMedicalHistory": {"type": "string"},
                "recommendations": {"type": "string"}
            },
            "required": ["consultation_id"]
        }
    }
}

TOOL_COMPLETE_CONSULTATION = {
    "type": "function",
    "function": {
        "name": "complete_consultation",
        "description": "Mark a consultation as COMPLETED.",
        "parameters": {
            "type": "object",
            "properties": {
                "consultation_id": {"type": "integer"}
            },
            "required": ["consultation_id"]
        }
    }
}

TOOL_CANCEL_CONSULTATION = {
    "type": "function",
    "function": {
        "name": "cancel_consultation",
        "description": "Cancel a consultation.",
        "parameters": {
            "type": "object",
            "properties": {
                "consultation_id": {"type": "integer"}
            },
            "required": ["consultation_id"]
        }
    }
}

TOOL_UPDATE_USER = {
    "type": "function",
    "function": {
        "name": "update_user",
        "description": "Update a user's role or status.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
                "data": {"type": "object"}
            },
            "required": ["user_id", "data"]
        }
    }
}
'''

with open("tools.py", "a") as f:
    f.write(extra_tools_code)
    
# Let's also update the get_tools_for_role function in tools.py
# First read the file
with open("tools.py", "r") as f:
    content = f.read()

# Replace the ALL_TOOLS list and roles in tools.py
import re

new_admin_tools = "TOOL_CREATE_CLINIC, TOOL_UPDATE_CLINIC, TOOL_DELETE_CLINIC, TOOL_CREATE_CONSULTATION, TOOL_UPDATE_CONSULTATION, TOOL_COMPLETE_CONSULTATION, TOOL_CANCEL_CONSULTATION, TOOL_UPDATE_USER"

# Since this is a bit complex, we will just use regex to append to the appropriate lists inside get_tools_for_role

content = content.replace("] # Return all for admin", f", {new_admin_tools}] # Return all for admin")
content = content.replace("TOOL_GET_CONSULTATION_WITH_TESTS,", f"TOOL_GET_CONSULTATION_WITH_TESTS, TOOL_UPDATE_CONSULTATION, TOOL_COMPLETE_CONSULTATION,")

with open("tools.py", "w") as f:
    f.write(content)
