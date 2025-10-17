from __future__ import annotations

import frappe


def after_install() -> None:
	ensure_module_def()
	ensure_workspace_visibility()
	ensure_navbar_shortcut()


def ensure_module_def() -> None:
	module_name = "Vulero Biometric Attendance"
	if frappe.db.exists("Module Def", module_name):
		return

	frappe.get_doc(
		{
			"doctype": "Module Def",
			"module_name": module_name,
			"app_name": "vulero_biometric_attendance",
		}
	).insert(ignore_permissions=True)


def ensure_workspace_visibility() -> None:
	"""Make sure the workspace is published."""
	if frappe.db.exists("Workspace", "Vulero Biometric Attendance"):
		frappe.db.set_value("Workspace", "Vulero Biometric Attendance", "public", 1)


def ensure_navbar_shortcut() -> None:
	"""Create a navbar settings entry for the Face Check-In shortcut if one does not exist."""
	settings = frappe.get_single("Navbar Settings")
	items = settings.get("settings_dropdown") or []
	label = "Face Check-In"
	route = "/app/biometric-checkin"

	for item in items:
		if item.item_label == label and (item.route or "").strip() == route:
			return

	settings.append(
		"settings_dropdown",
		{
			"item_label": label,
			"item_type": "Route",
			"route": route,
			"is_enabled": 1,
			"parent_label": "Modules",
			"open_in_new_tab": 0,
		},
	)
	settings.save(ignore_permissions=True)
