import frappe
from frappe.model.document import Document


class EmployeeBiometricSample(Document):
	"""Child table storing biometric templates captured during enrollment."""

	def autoname(self) -> None:
		if not self.sample_name:
			self.sample_name = frappe.generate_hash(length=8)
