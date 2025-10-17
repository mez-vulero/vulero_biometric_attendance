from __future__ import annotations

import json
from typing import List, Tuple

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint, now_datetime

from vulero_biometric_attendance.vulero_biometric_attendance.utils.biometric import (
	encode_image,
	invalidate_encoding_cache,
)

class EmployeeBiometricProfile(Document):
	"""Represents the set of biometric templates that identify an employee."""

	def autoname(self) -> None:
		if not self.name:
			self.name = make_autoname("EBP-.YYYY.-.#####")

	def before_insert(self) -> None:
		self._sync_employee_name()

	def validate(self) -> None:
		self._sync_employee_name()
		self._populate_missing_encodings()
		self._ensure_active_sample()
		self._ensure_encodings_serializable()

	def on_update(self) -> None:
		invalidate_encoding_cache()

	def on_trash(self) -> None:
		invalidate_encoding_cache()

	def _sync_employee_name(self) -> None:
		if self.employee:
			self.employee_name = frappe.db.get_value("Employee", self.employee, "employee_name")

	def _ensure_active_sample(self) -> None:
		active_samples = [sample for sample in self.biometric_samples if cint(sample.is_active)]
		if not active_samples:
			frappe.throw(_("At least one biometric sample must be active."))

	def _populate_missing_encodings(self) -> None:
		for sample in self.biometric_samples:
			if sample.encoding or not sample.image:
				continue

			image_bytes, file_doc = self._load_sample_file(sample.image)
			encoding, checksum = self._generate_encoding(image_bytes)

			sample.encoding = json.dumps(encoding)
			sample.encoding_checksum = checksum
			sample.captured_on = sample.captured_on or now_datetime()
			sample.captured_by = sample.captured_by or frappe.session.user
			sample.capture_source = sample.capture_source or "Webcam"

			if file_doc and self.name:
				file_doc.attached_to_doctype = self.doctype
				file_doc.attached_to_name = self.name
				file_doc.save(ignore_permissions=True)

	def _load_sample_file(self, file_url: str):
		file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
		if not file_name:
			frappe.throw(_("File {0} could not be found. Please capture the biometric sample again.").format(file_url))

		file_doc = frappe.get_doc("File", file_name)
		content = file_doc.get_content()
		if not content:
			frappe.throw(_("Captured image {0} is empty. Please recapture.").format(file_doc.file_name))

		if isinstance(content, str):
			content = content.encode()

		return content, file_doc

	def _generate_encoding(self, image_bytes: bytes) -> Tuple[list[float], str]:
		try:
			return encode_image(image_bytes)
		except frappe.ValidationError:
			raise
		except Exception as exc:  # pragma: no cover - defensive branch
			frappe.throw(_("Unable to process the captured image for biometric encoding."), exc=exc)

	def _ensure_encodings_serializable(self) -> None:
		for sample in self.biometric_samples:
			if not sample.encoding:
				frappe.throw(
					_("Biometric sample {0} is missing a face encoding. Capture before saving.").format(
						sample.sample_name or _("Unnamed Sample")
					)
				)
			try:
				values: List[float] = json.loads(sample.encoding)
			except json.JSONDecodeError as exc:
				frappe.throw(_("Encoding for sample {0} is not valid JSON.").format(sample.sample_name), exc=exc)

			if len(values) != 128:
				frappe.throw(
					_("Encoding for sample {0} is invalid. Expected 128 values, received {1}.").format(
						sample.sample_name, len(values)
					)
				)
