from __future__ import annotations

from typing import List

import frappe
from frappe.model.document import Document


class BiometricAttendanceSettings(Document):
	"""Singleton storing configuration for biometric check-ins."""

	def get_allowed_networks(self) -> List[str]:
		return [row.cidr for row in self.allowed_networks or []]


def get_settings() -> BiometricAttendanceSettings:
	return frappe.get_single("Biometric Attendance Settings")
