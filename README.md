### Vulero Biometric Attendance

Biometrics based checkin/out app that uses device camera and pre registered face biometric data to allow checking and out for employees

### Prerequisites

Install the system libraries required by [`face_recognition`](https://github.com/ageitgey/face_recognition):

```bash
sudo apt install build-essential cmake libopenblas-dev liblapack-dev libjpeg-dev libboost-all-dev
bench pip install face-recognition
```

The app automatically pulls the Python dependency via `pyproject.toml`, but the system packages must be present on every bench where the app runs.

If you regenerate assets yourself, build the bundle after installing:

```bash
bench build
```

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench install-app vulero_biometric_attendance
```

### Post-install Setup

All structural artefacts (module page, workspace, navbar shortcut) are created automatically during `install-app` and on every `bench migrate`. To finish the configuration, complete the steps below on the target site:

1. **Allowed networks**  
   Open **Biometric Attendance Settings** and add the CIDR ranges that should be able to perform face check-ins (for example `10.10.0.0/16` for an office LAN or `203.0.113.42/32` for a single public IP).  
   > Tip: For testing, you can allow `0.0.0.0/0` temporarily, but tighten it before going live.

2. **Reverse proxy headers**  
   If the site is served behind nginx (default bench setup) or another load balancer, forward the real client IP so the allow-list works.  
   Example snippet for nginx:
   ```nginx
   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   proxy_set_header X-Real-IP $remote_addr;
   proxy_set_header X-Forwarded-Proto $scheme;
   ```
   Reload nginx and clear the site cache:
   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   bench --site <your-site> clear-cache
   ```

3. **Face encodings**  
   Employees can open the **Face Check-In** workspace to enrol themselves. HR managers can review and approve profiles in the **Employee Biometric Profile** list. Only approved profiles participate in matching.

4. **Verification**  
   - Visit `/app/biometric-checkin`, start the camera, and take a test snapshot.  
   - Ensure the matching succeeds and the new log appears under **HR > Employee Checkin**.  
   - If the request is blocked with a 417 error, double-check the IP range and proxy headers.

### Key Features

- Employee-facing enrollment UI (camera capture) that stores face encodings in the new **Employee Biometric Profile** DocType.
- Secure IP allow-list via **Biometric Attendance Settings** to restrict usage to office networks.
- HR approval workflow with audit trail for biometric samples.
- REST endpoints for face enrollment and hands-free IN/OUT logging into Frappe HRMS Employee Checkin.

### Whitelisted API Methods

| Method | Description |
| --- | --- |
| `vulero_biometric_attendance.api.enroll_face_sample` | Accepts a base64 image, encodes it with `face_recognition`, and appends it to the caller's biometric profile. |
| `vulero_biometric_attendance.api.check_in_with_face` | Runs face verification, infers the next log type, and creates an `Employee Checkin` entry. |

Both endpoints enforce the Wi-Fi/IP restrictions defined in **Biometric Attendance Settings**.

### Troubleshooting Checklist

- **417 Expectation Failed** → The server cannot match the request IP to the allow-list. Confirm the public IP (`curl ifconfig.me`) is included and that the reverse proxy is forwarding the headers shown above.
- **Camera access denied** → Browser blocked media permissions. Grant access or trigger via desktop/mobile settings.
- **Multiple faces detected / No face detected** → Ensure only one person is within the frame and lighting is adequate.

### Testing

Unit tests can be added under `vulero_biometric_attendance/tests/`. Run them via:

```bash
bench --site <your-site> run-tests --app vulero_biometric_attendance
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/vulero_biometric_attendance
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
