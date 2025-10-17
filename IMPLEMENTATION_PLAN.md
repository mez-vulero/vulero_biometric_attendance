# Vulero Biometric Attendance – Implementation Plan

## 1. Data Model
- `Employee Biometric Profile` (new DocType) links one-to-one with `Employee`, stores status, meta audit, and a child table of biometric samples.
- `Employee Biometric Sample` (child DocType) holds each captured image, serialized face encoding (128 floats from `face_recognition`), metadata (source, captured by/on), checksum, and active flag.
- `Biometric Attendance Settings` (singleton) manages feature toggle, match threshold, candidate limit, and allowed office networks (child DocType `Biometric Attendance Network` with CIDR ranges).
- Hooks: when profiles change status to “Approved”, publish cache invalidation and notify background services (future step).

## 2. Face Recognition Utilities
- Add `face-recognition>=1.3.0` dependency in `pyproject.toml`. Document OS packages (`cmake`, `dlib`, `libopenblas-dev`, `libjpeg`, `libboost`) required for installations.
- Create utility module `vulero_biometric_attendance/utils/biometric.py`:
  - `encode_image(image_bytes)` → returns `(encoding: list[float], checksum: str)` using `face_recognition`.
  - `match_encoding(encoding, candidates, threshold)` → returns best match with distance.
  - Helpers to load employee encodings into cache (use Redis Site cache or Frappe caching layer).
- Use celery/queue job to process heavy encoding operations asynchronously during enrollment; synchronous fallback for small loads.

## 3. Enrollment Flow
- Desk Page `Employee Biometric Enrollment` (via `www/` or `public/js/`) accessible to Employees with self-permission.
- Front-end: WebRTC camera capture (fallback upload). Convert to base64, send to whitelisted API `vulero_biometric_attendance.api.capture_sample`.
- Server API:
  - Validate user is the linked Employee.
  - Enforce allowed IP ranges (see §5).
  - Store image file (File DocType), call `encode_image`, append to child table, mark sample pending approval.
  - Limit number of pending samples; allow employee to delete/resubmit before HR approval.
- HR Manager desk list/report to view profiles, compare captured images, approve/reject, optionally kick off re-encoding.

## 4. Check-in API Flow
- Whitelisted endpoint `vulero_biometric_attendance.api.check_in`:
  1. Authenticate session token (Frappe session or API key/secret).
  2. Validate request IP within allowed networks.
  3. Receive photo snapshot (base64) + optional metadata.
  4. Run `encode_image`, compare to cached encodings for active employees (only those with approved profiles).
  5. Determine employee + log type:
     - Fetch latest `Employee Checkin` to auto-toggle IN/OUT considering shift assignment (use HRMS shift utilities).
     - Validate against shift windows; mark `offshift` where needed.
  6. Create `Employee Checkin` record, backfill geolocation if provided; return success payload with log details.
- Enforce rate limiting per user/device (simple throttle using `frappe.cache` counters).

## 5. Network Enforcement
- Middleware helper `assert_allowed_network(request_ip)`:
  - Load CIDRs from `Biometric Attendance Settings`.
  - Support IPv4/IPv6 matching.
  - Provide clear error message if user is off-network.
- Reuse helper in enrollment and check-in endpoints; log denied attempts.

## 6. Front-end Pages
- `public/js/enrollment.js`: Camera capture, preview, re-take, progress indicator, call enrollment API.
- `public/js/checkin.js`: Similar UI, show shift info + last check-in/out, confirm success.
- Responsive layout using Frappe Desk or a custom SPA (depends on preference); ensure HTTPS for camera.
- Provide instructions and fallback manual link.

## 7. Background Jobs & Caching
- Scheduled job to refresh in-memory encoding cache (e.g., warm-up daily).
- Hooks:
  - `on_update` of `Employee Biometric Profile` to enqueue cache update.
  - `on_trash` to purge old encodings/files.
- Optionally track failed matches to lock profile after `n` attempts (increment `failed_attempts`, notify HR).

## 8. Testing Strategy
- Unit tests:
  - Encoding utility with sample images (mocked to avoid heavy load).
  - IP validation scenarios.
  - Shift toggle logic (simulate prior check-ins).
- Integration tests:
  - Enrollment API flow with uploaded image fixture.
  - Check-in API verifying record creation and IN/OUT resolution.
- Manual QA checklist: desktop/mobile camera, lighting conditions, latency, HR approval path, failure conditions.

## 9. Deployment & Ops Notes
- Document required system packages for `face_recognition` (Ubuntu: `sudo apt install build-essential cmake libopenblas-dev liblapack-dev libjpeg-dev libboost-all-dev`).
- Ensure site runs over HTTPS for camera access.
- Consider GPU/CPU sizing; `face_recognition` uses CPU but benefits from SIMD; configure worker queues accordingly.
- Plan for data privacy: restrict File DocType storage, ensure limited retention, potentially encrypt encoding data at rest.

## 10. Next Implementation Steps
1. Implement biometric utility module and settings accessors.
2. Build enrollment API + desk page.
3. Implement check-in API with shift logic and logging.
4. Add cache invalidation hooks and background jobs.
5. Write automated tests and developer docs (`README`/Help doc).

