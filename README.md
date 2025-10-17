### Vulero Biometric Attendance

Biometrics based checkin/out app that uses device camera and pre registered face biometric data to allow checking and out for employees

### Prerequisites

Install the system libraries required by [`face_recognition`](https://github.com/ageitgey/face_recognition):

```bash
sudo apt install build-essential cmake libopenblas-dev liblapack-dev libjpeg-dev libboost-all-dev
bench pip install face-recognition
```

The app automatically pulls the Python dependency via `pyproject.toml`, but the system packages must be present on every bench where the app runs.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench install-app vulero_biometric_attendance
```

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
