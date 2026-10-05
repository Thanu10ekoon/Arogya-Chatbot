"""
Unified HTTP client for calling Arogya backend microservices.
"""

import httpx
from config import (
    USER_SERVICE_URL,
    CLINIC_SERVICE_URL,
    QUEUE_SERVICE_URL,
    CONSULTATION_SERVICE_URL,
    MEDICAL_RECORDS_SERVICE_URL,
)

from auth_context import current_auth_token

TIMEOUT = 15.0


def _get_headers() -> dict:
    token = current_auth_token.get()
    if token:
        return {"Authorization": token}
    return {}



async def _get(url: str) -> dict | list | None:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, headers=_get_headers())
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        # Return structured error for better LLM handling
        return {
            "error": f"Backend service error (HTTP {e.response.status_code})",
            "url": url,
            "status_code": e.response.status_code,
            "message": "The backend service encountered an error. This endpoint may not be implemented correctly or the data may not exist."
        }
    except httpx.TimeoutException:
        return {
            "error": "Request timeout",
            "url": url,
            "message": "The backend service took too long to respond."
        }
    except Exception as e:
        return {
            "error": "Connection failed",
            "url": url,
            "message": f"Could not connect to backend service: {str(e)}"
        }


async def _post(url: str, json_body: dict | list | None = None) -> dict | list | None:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(url, json=json_body, headers=_get_headers())
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        return {
            "error": f"Backend service error (HTTP {e.response.status_code})",
            "url": url,
            "status_code": e.response.status_code,
            "message": "The backend service encountered an error."
        }
    except httpx.TimeoutException:
        return {
            "error": "Request timeout",
            "url": url,
            "message": "The backend service took too long to respond."
        }
    except Exception as e:
        return {
            "error": "Connection failed",
            "url": url,
            "message": f"Could not connect to backend service: {str(e)}"
        }

async def _put(url: str, json_body: dict | list | None = None) -> dict | list | None:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.put(url, json=json_body, headers=_get_headers())
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        return {
            "error": f"Backend service error (HTTP {e.response.status_code})",
            "url": url,
            "status_code": e.response.status_code,
            "message": "The backend service encountered an error during update."
        }
    except Exception as e:
        return {"error": "Connection failed", "url": url, "message": str(e)}

async def _delete(url: str) -> dict | list | None:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.delete(url, headers=_get_headers())
            resp.raise_for_status()
            return {"status": "success", "message": "Deleted successfully"}
    except httpx.HTTPStatusError as e:
        return {
            "error": f"Backend service error (HTTP {e.response.status_code})",
            "url": url,
            "status_code": e.response.status_code,
            "message": "The backend service encountered an error during deletion."
        }
    except Exception as e:
        return {"error": "Connection failed", "url": url, "message": str(e)}

#  User Service 

async def get_all_users():
    return await _get(f"{USER_SERVICE_URL}/users/getAllUsers")


async def get_user(user_id: int):
    return await _get(f"{USER_SERVICE_URL}/users/getUser/{user_id}")


#  Patient Profiles 

async def get_all_patients():
    return await _get(f"{USER_SERVICE_URL}/patient_profile/getAllPatientProfiles")


async def get_patient_profile_by_user_id(user_id: int):
    return await _get(f"{USER_SERVICE_URL}/patient_profile/getPatientProfileByUserId/{user_id}")


#  Doctor Profiles 

async def get_all_doctors():
    return await _get(f"{USER_SERVICE_URL}/doctor_profile/getAllDoctorProfiles")


async def get_doctor_profile_by_user_id(user_id: int):
    return await _get(f"{USER_SERVICE_URL}/doctor_profile/getDoctorProfileByUserId/{user_id}")


async def get_doctor_profile(doctor_id: int):
    return await _get(f"{USER_SERVICE_URL}/doctor_profile/getDoctorProfile/{doctor_id}")


#  Admin / Technician Profiles 

async def get_all_admins():
    return await _get(f"{USER_SERVICE_URL}/admin_profile/getAllAdminProfiles")


async def get_all_technicians():
    return await _get(f"{USER_SERVICE_URL}/technician_profile/getAllTechnicianProfiles")


async def get_admin_profile_by_user_id(user_id: int):
    return await _get(f"{USER_SERVICE_URL}/admin_profile/getAdminProfileByUserId/{user_id}")


#  Clinic Service 

async def get_all_clinics():
    return await _get(f"{CLINIC_SERVICE_URL}/clinics/getAllClinics")


async def get_clinic(clinic_id: int):
    return await _get(f"{CLINIC_SERVICE_URL}/clinics/getClinic/{clinic_id}")


async def get_clinic_doctors(clinic_id: int):
    return await _get(f"{CLINIC_SERVICE_URL}/clinic_doctors/getClinicDoctorsByClinicId/{clinic_id}")


async def get_all_clinic_doctors():
    return await _get(f"{CLINIC_SERVICE_URL}/clinic_doctors/getAllClinicDoctors")


#  Queue Service 

async def get_clinic_queue(clinic_id: str):
    return await _get(f"{QUEUE_SERVICE_URL}/queue/clinics/{clinic_id}/tokens")


async def get_queue_token(token_id: int):
    return await _get(f"{QUEUE_SERVICE_URL}/queue/tokens/{token_id}")


#  Consultation Service 

async def get_consultation(consultation_id: int):
    return await _get(f"{CONSULTATION_SERVICE_URL}/consultations/{consultation_id}")


async def get_consultations(
    patient_id: int | None = None,
    doctor_id: int | None = None,
    clinic_id: int | None = None,
    status: str | None = None,
):
    params = {}
    if patient_id is not None:
        params["patientId"] = patient_id
    if doctor_id is not None:
        params["doctorId"] = doctor_id
    if clinic_id is not None:
        params["clinicId"] = clinic_id
    if status is not None:
        params["status"] = status
    params["size"] = 200  # fetch enough for analysis
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{CONSULTATION_SERVICE_URL}/consultations"
    if qs:
        url += f"?{qs}"
    print(f"[DEBUG] Fetching consultations: {url}")
    data = await _get(url)
    # backend returns Page<T> with a 'content' field
    if isinstance(data, dict) and "content" in data:
        print(f"[DEBUG] Found {len(data['content'])} consultations")
        return data["content"]
    print(f"[DEBUG] Consultation response type: {type(data)}, is list: {isinstance(data, list)}")
    if isinstance(data, list):
        print(f"[DEBUG] Found {len(data)} consultations (direct list)")
    return data


async def get_consultation_with_tests(consultation_id: int):
    return await _get(f"{CONSULTATION_SERVICE_URL}/consultations/{consultation_id}/with-tests")


#  Lab Tests 

async def get_lab_tests(
    status: str | None = None,
    technician_id: int | None = None,
):
    params: dict = {"size": 200}
    if status:
        params["status"] = status
    if technician_id:
        params["technicianId"] = technician_id
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{CONSULTATION_SERVICE_URL}/lab-tests?{qs}"
    data = await _get(url)
    if isinstance(data, dict) and "content" in data:
        return data["content"]
    return data


async def get_lab_tests_by_consultation(consultation_id: int):
    return await _get(f"{CONSULTATION_SERVICE_URL}/lab-tests/consultation/{consultation_id}")


#  Medical Records Service 

async def get_test_results_by_patient(patient_id: int):
    return await _get(f"{MEDICAL_RECORDS_SERVICE_URL}/test-results/patient/{patient_id}")


async def get_test_result(test_result_id: int):
    return await _get(f"{MEDICAL_RECORDS_SERVICE_URL}/test-results/{test_result_id}")


async def get_test_result_by_lab_test(lab_test_id: int):
    return await _get(f"{MEDICAL_RECORDS_SERVICE_URL}/test-results/lab-test/{lab_test_id}")


async def get_all_test_results():
    params = {"size": 200, "sortBy": "createdAt", "sortDir": "DESC"}
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{MEDICAL_RECORDS_SERVICE_URL}/test-results?{qs}"
    data = await _get(url)
    if isinstance(data, dict) and "content" in data:
        return data["content"]
    return data


async def create_clinic(data: dict):
    if "doctorIds" not in data:
        data["doctorIds"] = []
    return await _post(f"{CLINIC_SERVICE_URL}/clinics/createClinic", data)

async def update_clinic(clinic_id: int, data: dict):
    return await _put(f"{CLINIC_SERVICE_URL}/clinics/updateClinic", data)

async def delete_clinic(clinic_id: int):
    return await _delete(f"{CLINIC_SERVICE_URL}/clinics/deleteClinic/{clinic_id}")

async def create_consultation(data: dict):
    return await _post(f"{CONSULTATION_SERVICE_URL}/consultations", data)

async def update_consultation(consultation_id: int, data: dict):
    return await _put(f"{CONSULTATION_SERVICE_URL}/consultations/{consultation_id}", data)

async def complete_consultation(consultation_id: int):
    return await _post(f"{CONSULTATION_SERVICE_URL}/consultations/{consultation_id}/complete")

async def cancel_consultation(consultation_id: int):
    return await _post(f"{CONSULTATION_SERVICE_URL}/consultations/{consultation_id}/cancel")

async def create_lab_test(data: dict):
    return await _post(f"{CONSULTATION_SERVICE_URL}/lab-tests", data)

async def update_lab_test(lab_test_id: int, data: dict):
    return await _put(f"{CONSULTATION_SERVICE_URL}/lab-tests/{lab_test_id}", data)

async def update_lab_test_status(lab_test_id: int, data: dict):
    return await _put(f"{CONSULTATION_SERVICE_URL}/lab-tests/{lab_test_id}/status", data)

async def delete_lab_test(lab_test_id: int):
    return await _delete(f"{CONSULTATION_SERVICE_URL}/lab-tests/{lab_test_id}")

async def create_test_result(data: dict):
    return await _post(f"{MEDICAL_RECORDS_SERVICE_URL}/test-results", data)

async def update_test_result(test_result_id: int, data: dict):
    return await _put(f"{MEDICAL_RECORDS_SERVICE_URL}/test-results/{test_result_id}", data)

async def delete_test_result(test_result_id: int):
    return await _delete(f"{MEDICAL_RECORDS_SERVICE_URL}/test-results/{test_result_id}")

async def update_user(user_id: int, data: dict):
    return await _put(f"{USER_SERVICE_URL}/users/updateUser", data)
