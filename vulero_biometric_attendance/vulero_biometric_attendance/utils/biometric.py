from __future__ import annotations

import base64
import hashlib
import io
import json
import numpy as np
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import frappe
from frappe import _
from frappe.utils import cint

from vulero_biometric_attendance.vulero_biometric_attendance.doctype.biometric_attendance_settings.biometric_attendance_settings import (
	get_settings,
)

try:
	import face_recognition  # type: ignore
except ImportError as exc:  # pragma: no cover - runtime guard
	face_recognition = None  # type: ignore[assignment]
	_import_error = exc
else:
	_import_error = None


CACHE_KEY = "vulero_biometric_attendance:face_encodings"


class BiometricDependencyMissing(frappe.ValidationError):
	"""Raised when the face_recognition dependency is not available."""


@dataclass(frozen=True)
class EncodingCandidate:
	employee: str
	profile: str
	sample: str
	encoding: Sequence[float]


def ensure_library_available() -> None:
	if face_recognition is None:  # pragma: no cover - executed when dependency missing
		message = _("face_recognition library could not be imported. Install system dependencies and run bench pip install face-recognition.")
		raise BiometricDependencyMissing(message) from _import_error


def decode_image(data_url: str | None) -> bytes:
	if not data_url:
		frappe.throw(_("No image data provided."))

	try:
		header, encoded = data_url.split(",", 1)
	except ValueError:
		encoded = data_url
	file_bytes = base64.b64decode(encoded)
	if not file_bytes:
		frappe.throw(_("Captured image is empty. Please try again."))
	return file_bytes


def encode_image(image_content: bytes) -> tuple[list[float], str]:
	ensure_library_available()

	image = face_recognition.load_image_file(io.BytesIO(image_content))
	encodings = face_recognition.face_encodings(image)
	if not encodings:
		frappe.throw(_("No face detected in the captured image. Please try again."))
	if len(encodings) > 1:
		frappe.throw(_("Multiple faces detected. Capture a photo with a single face."))

	encoding_vector = encodings[0].tolist()
	encoding_checksum = hashlib.sha256(json.dumps(encoding_vector).encode("utf-8")).hexdigest()

	return encoding_vector, encoding_checksum


def match_encoding(
	source_encoding: Sequence[float],
	candidates: Iterable[EncodingCandidate],
	threshold: float,
) -> tuple[EncodingCandidate, float] | tuple[None, None]:
	ensure_library_available()

	candidates = list(candidates)
	if not candidates:
		return None, None

	encoding_vectors: list[np.ndarray] = []
	valid_candidates: list[EncodingCandidate] = []
	for candidate in candidates:
		vector = np.array(candidate.encoding, dtype="float64")
		if vector.shape[0] != 128:
			continue
		encoding_vectors.append(vector)
		valid_candidates.append(candidate)

	if not encoding_vectors:
		return None, None

	source_array = np.array(list(source_encoding), dtype="float64")
	if source_array.shape[0] != 128:
		frappe.throw(_("Captured encoding is invalid. Please retry the capture."))

	enc_matrix = np.stack(encoding_vectors, axis=0)
	distances = face_recognition.face_distance(enc_matrix, source_array)

	best_index = int(distances.argmin())
	best_distance = float(distances[best_index])
	best_candidate = valid_candidates[best_index]

	if best_distance <= threshold:
		return best_candidate, best_distance

	return None, None


def load_encoding_cache(force: bool = False) -> list[EncodingCandidate]:
	cache = frappe.cache()
	if force:
		cache.delete_value(CACHE_KEY)

	cached = cache.get_value(CACHE_KEY)
	if cached:
		return [EncodingCandidate(**candidate) for candidate in json.loads(cached)]

	profiles = frappe.get_all(
		"Employee Biometric Profile",
		fields=["name", "employee", "status"],
		filters={"status": "Approved"},
	)
	candidates: list[EncodingCandidate] = []

	for profile in profiles:
		doc = frappe.get_doc("Employee Biometric Profile", profile.name)
		for sample in doc.biometric_samples or []:
			if not cint(sample.is_active) or not sample.encoding:
				continue
			try:
				values: List[float] = json.loads(sample.encoding)  # type: ignore[assignment]
			except json.JSONDecodeError:
				continue
			candidates.append(
				EncodingCandidate(
					employee=doc.employee,
					profile=doc.name,
					sample=sample.sample_name or sample.name,
					encoding=values,
				)
			)

	cache.set_value(
		CACHE_KEY,
		json.dumps([candidate.__dict__ for candidate in candidates]),
	)
	return candidates


def invalidate_encoding_cache() -> None:
	frappe.cache().delete_value(CACHE_KEY)


def assert_allowed_network(ip_address: str | None = None) -> None:
	settings = get_settings()
	if not settings.enabled:
		return

	allowed_networks = settings.get_allowed_networks()
	if not allowed_networks:
		return

	ip = ip_address or getattr(frappe.local, "request_ip", None)
	request = getattr(frappe.local, "request", None)

	if request:
		headers = getattr(request, "headers", {})
		forwarded_for = None
		if headers:
			forwarded_for = headers.get("X-Forwarded-For") or headers.get("X_FORWARDED_FOR")
		if forwarded_for:
			ip = forwarded_for.split(",")[0].strip()
		elif headers and headers.get("X-Real-IP"):
			ip = headers.get("X-Real-IP")
		elif not ip:
			ip = getattr(request, "remote_addr", None)

	if not ip:
		frappe.throw(_("Unable to determine your IP address. Please try again from the office network."))

	import ipaddress

	try:
		request_ip = ipaddress.ip_address(ip)
	except ValueError:
		# strip port information if present (e.g., "192.168.1.10:50234")
		if ":" in ip and ip.count(":") == 1:
			ip = ip.split(":", 1)[0]
			request_ip = ipaddress.ip_address(ip)
		else:
			frappe.throw(_("Unable to interpret IP address {0}." ).format(ip))

	if request_ip.is_loopback:
		return

	for network in allowed_networks:
		try:
			if request_ip in ipaddress.ip_network(network, strict=False):
				return
		except ValueError:
			continue

	frappe.throw(_("Biometric check-ins are restricted to the approved office network. Please connect to the office Wi-Fi."))
