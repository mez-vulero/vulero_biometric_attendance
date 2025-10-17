from __future__ import annotations

import json
from typing import Any, Dict

import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.utils.file_manager import save_file

from hrms.hr.doctype.shift_assignment.shift_assignment import get_actual_start_end_datetime_of_shift

from vulero_biometric_attendance.vulero_biometric_attendance.doctype.biometric_attendance_settings.biometric_attendance_settings import (
    get_settings,
)
from vulero_biometric_attendance.vulero_biometric_attendance.doctype.employee_biometric_profile.employee_biometric_profile import (
    EmployeeBiometricProfile,
)
from vulero_biometric_attendance.vulero_biometric_attendance.utils.biometric import (
    assert_allowed_network,
    decode_image,
    encode_image,
    invalidate_encoding_cache,
    load_encoding_cache,
    match_encoding,
)


def _resolve_employee(target_employee: str | None = None) -> str:
	if target_employee:
		if not frappe.has_permission("Employee Biometric Profile", ptype="write"):
			frappe.throw(_("You are not permitted to manage biometric data for other employees."))
		if not frappe.db.exists("Employee", target_employee):
			frappe.throw(_("Employee {0} does not exist.").format(target_employee))
		return target_employee

	session_user = frappe.session.user
	if session_user in ("Guest", None):
		frappe.throw(_("Please sign in to continue."))

	employee = frappe.db.get_value("Employee", {"user_id": session_user}, "name")
	if not employee:
		frappe.throw(_("Your user account is not linked to an Employee record."))
	return employee


def _get_or_create_profile(employee: str) -> EmployeeBiometricProfile:
	profile_name = frappe.db.exists("Employee Biometric Profile", {"employee": employee})
	if profile_name:
		return frappe.get_doc("Employee Biometric Profile", profile_name)

	profile = frappe.get_doc(
		{
			"doctype": "Employee Biometric Profile",
			"employee": employee,
			"status": "Pending Approval",
		}
	)
	profile.insert()
	return profile


def _save_capture_file(file_bytes: bytes, profile: EmployeeBiometricProfile) -> str:
	filename = f"biometric-{profile.employee}-{now_datetime().strftime('%Y%m%d%H%M%S')}.jpg"
	file_doc = save_file(
		filename,
		file_bytes,
		doctype=profile.doctype,
		name=profile.name,
		is_private=1,
		decode=False,
	)
	return file_doc.file_url


@frappe.whitelist()
def enroll_face_sample(
	image: str,
	capture_source: str | None = None,
	sample_name: str | None = None,
	employee: str | None = None,
) -> Dict[str, Any]:
	assert_allowed_network()
	target_employee = _resolve_employee(employee)

	file_bytes = decode_image(image)
	encoding, checksum = encode_image(file_bytes)

	profile = _get_or_create_profile(target_employee)
	sample_label = sample_name or now_datetime().strftime("Sample-%Y%m%d-%H%M%S")

	if any(row.encoding_checksum == checksum for row in profile.biometric_samples or []):
		frappe.throw(_("This biometric sample is already registered. Capture a different image."))

	image_url = _save_capture_file(file_bytes, profile)

	child = profile.append(
		"biometric_samples",
		{
			"sample_name": sample_label,
			"image": image_url,
			"encoding": json.dumps(encoding),
			"encoding_checksum": checksum,
			"captured_on": now_datetime(),
			"captured_by": frappe.session.user,
			"capture_source": capture_source or "Webcam",
			"is_active": 1,
		},
	)

	if profile.status != "Approved":
		profile.status = "Pending Approval"

	profile.save()
	if profile.status == "Approved":
		invalidate_encoding_cache()

	return {
		"profile": profile.name,
		"employee": target_employee,
		"sample": child.sample_name,
		"status": profile.status,
		"image_url": image_url,
	}


@frappe.whitelist()
def check_in_with_face(
	image: str,
	latitude: float | None = None,
	longitude: float | None = None,
	device_id: str | None = None,
) -> Dict[str, Any]:
	from hrms.hr.doctype.employee_checkin.employee_checkin import EmployeeCheckin

	assert_allowed_network()

	settings = get_settings()
	if not settings.enabled:
		frappe.throw(_("Biometric attendance is currently disabled."))

	file_bytes = decode_image(image)
	source_encoding, checksum = encode_image(file_bytes)

	candidates = load_encoding_cache()
	if not candidates:
		frappe.throw(_("No approved biometric profiles found. Contact your HR administrator."))

	threshold = settings.confidence_threshold or 0.55
	candidate, distance = match_encoding(source_encoding, candidates, threshold)
	if not candidate:
		frappe.throw(_("Face not recognized. Please try again or contact HR."))

	employee = candidate.employee
	log_type = _determine_log_type(employee)

	doc: EmployeeCheckin = frappe.new_doc("Employee Checkin")
	doc.employee = employee
	doc.log_type = log_type
	doc.time = now_datetime()
	doc.device_id = device_id
	if latitude is not None:
		doc.latitude = latitude
	if longitude is not None:
		doc.longitude = longitude
	doc.insert()

	frappe.db.set_value(
		"Employee Biometric Profile",
		candidate.profile,
		{
			"last_verified_on": doc.time,
			"last_verified_by": frappe.session.user,
		},
		update_modified=False,
	)

	return {
		"employee": employee,
		"profile": candidate.profile,
		"sample": candidate.sample,
		"log_type": log_type,
		"time": doc.time,
		"checkin": doc.name,
		"distance": distance,
		"encoding_checksum": checksum,
	}


def _determine_log_type(employee: str) -> str:
	last_log = frappe.db.get_all(
		"Employee Checkin",
		filters={"employee": employee},
		fields=["name", "log_type"],
		order_by="time desc",
		limit=1,
	)
	if not last_log:
		return "IN"
	return "OUT" if last_log[0].log_type == "IN" else "IN"


@frappe.whitelist()
def get_check_in_status(employee: str | None = None) -> Dict[str, Any]:
    target_employee = _resolve_employee(employee)

    latest = frappe.db.get_all(
        "Employee Checkin",
        filters={"employee": target_employee},
        fields=["name", "log_type", "time", "shift"],
        order_by="time desc",
        limit=1,
    )
    status: Dict[str, Any] = {
        "employee": target_employee,
        "employee_name": frappe.db.get_value("Employee", target_employee, "employee_name"),
        "last_log": latest[0] if latest else None,
    }

    status["next_log_type"] = (
        "IN" if not latest else ("OUT" if latest[0].log_type == "IN" else "IN")
    )

    shift_info: Dict[str, Any] | None = None
    current_time = now_datetime()
    shift_details = get_actual_start_end_datetime_of_shift(target_employee, current_time, True)
    if shift_details:
        shift_info = {
            "name": shift_details.shift_type.name,
            "start": shift_details.start_datetime,
            "end": shift_details.end_datetime,
            "actual_start": shift_details.actual_start,
            "actual_end": shift_details.actual_end,
        }

    status["shift"] = shift_info
    status["server_time"] = current_time

    return status
