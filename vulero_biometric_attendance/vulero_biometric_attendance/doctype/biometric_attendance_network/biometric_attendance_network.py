from __future__ import annotations

import ipaddress

import frappe
from frappe import _
from frappe.model.document import Document


class BiometricAttendanceNetwork(Document):
	"""Child table row describing an allowed IP network for biometric actions."""

	def validate(self) -> None:
		try:
			ipaddress.ip_network(self.cidr, strict=False)
		except ValueError:
			frappe.throw(_("CIDR range {0} is invalid.").format(self.cidr))
