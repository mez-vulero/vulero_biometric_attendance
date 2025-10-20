frappe.provide("vulero_biometric_attendance.pages");

frappe.pages["biometric-checkin"].on_page_load = function (wrapper) {
	wrapper.biometric_checkin = new vulero_biometric_attendance.pages.BiometricCheckin(wrapper);
};

vulero_biometric_attendance.pages.BiometricCheckin = class {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: this.wrapper,
			title: __("Biometric Check-In"),
			single_column: true,
		});
		this.stream = null;
		this.next_log_type = "IN";
		this.capture_in_progress = false;

		this.make_body();
		this.bind_events();
		this.fetch_status();
	}

	make_body() {
		this.$body = $(
			`<div class="biometric-checkin-page">
				<div class="biometric-checkin-card shadow-sm">
				<div class="live-status alert alert-secondary" data-field="live-status">${__("Initializing…")}</div>
				<div class="checkin-status">
					<div class="status-label">${__("Next Action")}</div>
					<div class="status-value" data-field="next-action">${__("Loading...")}</div>
					<div class="status-detail" data-field="last-log"></div>
				</div>
				<div class="shift-status">
					<div class="status-label">${__("Shift Window")}</div>
					<div class="status-value" data-field="shift-window">${__("Checking assignments...")}</div>
					<div class="status-detail" data-field="shift-progress"></div>
				</div>
				<div class="camera-container">
					<video autoplay playsinline muted></video>
					<canvas style="display:none;"></canvas>
				</div>
				<div class="actions">
					<button class="btn btn-secondary" data-action="start-camera">${__("Start Camera")}</button>
					<button class="btn btn-primary" data-action="capture" disabled>${__("Capture & Check-In")}</button>
					<button class="btn btn-default" data-action="stop-camera" disabled>${__("Stop Camera")}</button>
				</div>
				<div class="help-text text-muted">${__("Ensure you are connected to the office network before attempting a check-in.")}</div>
				</div>
			</div>`
		);

		this.video = this.$body.find("video")[0];
		this.canvas = this.$body.find("canvas")[0];

		this.page.main.append(this.$body);
	}

	bind_events() {
		this.$body.find('[data-action="start-camera"]').on("click", () => this.start_camera());
		this.$body.find('[data-action="capture"]').on("click", () => this.capture_and_checkin());
		this.$body.find('[data-action="stop-camera"]').on("click", () => this.stop_camera());

		this.page.set_primary_action(__("Refresh Status"), () => this.fetch_status(true));
	}

	async start_camera() {
		if (this.stream) {
			this.set_status(__("Camera already running."), "warning");
			return;
		}
		try {
			this.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
			this.video.srcObject = this.stream;
			this.video.style.transform = "scaleX(-1)";
			this.set_camera_buttons(true);
			this.set_status(__("Camera ready. Position your face within the frame."), "info");
		} catch (error) {
			console.error(error);
			frappe.msgprint({
				title: __("Camera Access Denied"),
				message: __("We were unable to access your camera. Please grant permission and try again."),
				indicator: "red",
			});
			this.set_status(__("Camera access denied. Please allow permissions and retry."), "danger");
		}
	}

	stop_camera() {
		if (!this.stream) {
			return;
		}
		this.stream.getTracks().forEach((track) => track.stop());
		this.stream = null;
		this.video.srcObject = null;
		this.video.style.transform = "";
		this.set_camera_buttons(false);
		this.set_status(__("Camera stopped."), "muted");
	}

	set_camera_buttons(is_active) {
		this.$body.find('[data-action="start-camera"]').prop("disabled", is_active);
		this.$body.find('[data-action="capture"]').prop("disabled", !is_active || this.capture_in_progress);
		this.$body.find('[data-action="stop-camera"]').prop("disabled", !is_active);
	}

	fetch_status(show_alert = false) {
		frappe.call({
			method: "vulero_biometric_attendance.api.get_check_in_status",
			freeze: show_alert,
		}).then((r) => {
			if (!r.message) {
				return;
			}
			const { employee_name, last_log, next_log_type, shift, server_time } = r.message;
			this.next_log_type = next_log_type;
			this.$body
				.find('[data-field="next-action"]')
				.text(__("{0} ({1})", [next_log_type, employee_name || ""]))
				.toggleClass("text-success", next_log_type === "IN")
				.toggleClass("text-warning", next_log_type === "OUT");

			const $detail = this.$body.find('[data-field="last-log"]');
			if (last_log) {
				const when = frappe.datetime.user_to_str(last_log.time) || last_log.time;
				$detail.text(
					__("Last {0} at {1}{2}", [
						last_log.log_type,
						when,
						last_log.shift ? __(" (Shift: {0})", [last_log.shift]) : "",
					])
				);
			} else {
				$detail.text(__("No previous check-ins found."));
			}

			this.render_shift_details(shift, server_time);
		});
	}

	render_shift_details(shift, server_time) {
		const $window = this.$body.find('[data-field="shift-window"]');
		const $progress = this.$body.find('[data-field="shift-progress"]');

		if (!shift) {
			$window.text(__("No active shift assigned today."));
			$progress.text("");
			return;
		}

		const startTimestamp = shift.actual_start || shift.start;
		const endTimestamp = shift.actual_end || shift.end;
		const startMoment = moment(startTimestamp);
		const endMoment = moment(endTimestamp);
		const nowMoment = server_time ? moment(server_time) : moment();

		const formattedWindow = `${frappe.datetime.str_to_user(startTimestamp)} – ${frappe.datetime.str_to_user(endTimestamp)}`;
		$window.text(`${shift.name || __("Shift")}: ${formattedWindow}`);

		let progressText;
		if (nowMoment.isBefore(startMoment)) {
			const minutesUntil = Math.ceil(startMoment.diff(nowMoment, "minutes", true));
			progressText = __("Starts in {0} minutes", [minutesUntil]);
		} else if (nowMoment.isBetween(startMoment, endMoment)) {
			const minutesElapsed = Math.floor(nowMoment.diff(startMoment, "minutes", true));
			const minutesRemaining = Math.max(Math.ceil(endMoment.diff(nowMoment, "minutes", true)), 0);
			progressText = __("{0} minutes elapsed • {1} minutes remaining", [minutesElapsed, minutesRemaining]);
		} else {
			const minutesAgo = Math.ceil(nowMoment.diff(endMoment, "minutes", true));
			progressText = __("Shift ended {0} minutes ago", [minutesAgo]);
		}

		$progress.text(progressText);
	}

	capture_frame() {
		const video = this.video;
		if (!video || !video.videoWidth) {
			throw new Error("Camera stream not ready");
		}
		const canvas = this.canvas;
		canvas.width = video.videoWidth;
		canvas.height = video.videoHeight;
		const context = canvas.getContext("2d");
		context.drawImage(video, 0, 0, canvas.width, canvas.height);
		return canvas.toDataURL("image/jpeg", 0.9);
	}

	capture_and_checkin() {
		if (!this.stream) {
			frappe.msgprint({
				indicator: "orange",
				message: __("Start your camera before capturing."),
				title: __("Camera not active"),
			});
			return;
		}

		let snapshot;
		try {
			snapshot = this.capture_frame();
		} catch (error) {
			frappe.msgprint({
				indicator: "red",
				message: __("Unable to capture an image from your camera."),
				title: __("Capture Failed"),
			});
			return;
		}

		this.capture_in_progress = true;
		this.set_camera_buttons(true);
		this.set_status(__("Matching face data…"), "info");

		const request = frappe.call({
			method: "vulero_biometric_attendance.api.check_in_with_face",
			args: {
				image: snapshot,
			},
			freeze: true,
			freeze_message: __("Verifying face and logging attendance..."),
		});

		request.then(function (r) {
			if (!r.message) {
				return;
			}
			const { log_type, time, distance } = r.message;
			this.fetch_status();
			this.stop_camera();
			this.set_status(__("{0} recorded at {1}", [log_type, frappe.datetime.user_to_str(time) || time]), "success");
			frappe.show_alert({
				message: __("Recorded {0} at {1} (match score: {2})", [
					log_type,
					frappe.datetime.user_to_str(time) || time,
					distance !== null && distance !== undefined ? distance.toFixed(3) : "--",
				]),
				indicator: "green",
			});
		});

		request.fail(function (error) {
			this.stop_camera();
			console.error(error);
			const message = error && error.exc ? error.exc.split("\n").pop() : __("Unable to complete check-in. Please try again.");
			this.set_status(message, "danger");
			frappe.msgprint({
				indicator: "red",
				message,
				title: __("Check-In Failed"),
			});
		});

		request.always(function () {
			this.capture_in_progress = false;
			if (this.stream) {
				this.set_camera_buttons(true);
			} else {
				this.set_camera_buttons(false);
			}
		});
	}

	set_status(message, tone = "info") {
		const toneClasses = {
			info: "alert-info",
			success: "alert-success",
			warning: "alert-warning",
			danger: "alert-danger",
			muted: "alert-secondary",
		};

		const $status = this.$body.find('[data-field="live-status"]');
		$status.removeClass("alert-info alert-success alert-warning alert-danger alert-secondary");
		$status.addClass(toneClasses[tone] || "alert-info");
		$status.text(message);
	}
};
