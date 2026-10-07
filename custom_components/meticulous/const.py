"""Constants for the Meticulous integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "meticulous"

CONF_TOKEN = "token"
CONF_ALLOW_DANGEROUS_ACTIONS = "allow_dangerous_actions"
CONF_METICAI_URL = "meticai_url"
# The machine serves its REST + socket.io API on plain HTTP port 80 (8080 is closed on
# current firmware, verified 2026-10-07 on firmware 0.2.24).
DEFAULT_PORT = 80

# Socket telemetry older than this triggers a reconnect attempt.
TELEMETRY_STALE_SECONDS = 30
METICAI_REFRESH_INTERVAL = timedelta(seconds=60)
METICAI_ANALYSIS_TIMEOUT_SECONDS = 600

COORDINATOR_UPDATE_INTERVAL = timedelta(seconds=5)

PLATFORMS: list[str] = ["sensor", "binary_sensor", "button", "switch", "select"]

ATTR_TEMPERATURE = "temperature"
ATTR_PRESSURE = "pressure"
ATTR_FLOW_RATE = "flow_rate"
ATTR_SCALE_WEIGHT = "scale_weight"
ATTR_MOTOR_LOAD = "motor_load"
ATTR_BREW_STATE = "brew_state"
ATTR_MACHINE_STATE = "machine_state"
ATTR_AUTO_PURGE = "auto_purge"
ATTR_ACTIVE_PROFILE = "active_profile"
ATTR_AVAILABLE_PROFILES = "available_profiles"
ATTR_DANGEROUS_ARMED_REMAINING = "dangerous_armed_remaining"

ATTR_DEVICE_NAME = "device_name"
ATTR_DEVICE_HOSTNAME = "device_hostname"
ATTR_DEVICE_SERIAL = "device_serial"
ATTR_DEVICE_BATCH_NUMBER = "device_batch_number"
ATTR_DEVICE_BUILD_DATE = "device_build_date"
ATTR_DEVICE_FIRMWARE = "device_firmware"
ATTR_DEVICE_SOFTWARE_VERSION = "device_software_version"
ATTR_DEVICE_IMAGE_BUILD_CHANNEL = "device_image_build_channel"
ATTR_DEVICE_IMAGE_VERSION = "device_image_version"
ATTR_DEVICE_MAIN_VOLTAGE = "device_main_voltage"
ATTR_DEVICE_MANUFACTURING = "device_manufacturing"
ATTR_DEVICE_VERSION_HISTORY = "device_version_history"
ATTR_DEVICE_REPOSITORY_INFO = "device_repository_info"

ATTR_STATS_TOTAL_SAVED_SHOTS = "stats_total_saved_shots"
ATTR_STATS_BY_PROFILE = "stats_by_profile"

ATTR_METICAI_AVAILABLE = "meticai_available"
ATTR_METICAI_VERSION = "meticai_version"
ATTR_METICAI_UPDATE_AVAILABLE = "meticai_update_available"
ATTR_LAST_SHOT_PROFILE = "last_shot_profile"
ATTR_LAST_SHOT_TIME = "last_shot_time"
ATTR_LAST_SHOT_WEIGHT = "last_shot_weight"
ATTR_LAST_SHOT_DURATION = "last_shot_duration"
ATTR_LAST_SHOT_DATE = "last_shot_date"
ATTR_LAST_SHOT_FILENAME = "last_shot_filename"
ATTR_LAST_ANALYSIS = "last_analysis"
ATTR_LAST_ANALYSIS_SUMMARY = "last_analysis_summary"
ATTR_LAST_ANALYSIS_SHOT = "last_analysis_shot"
ATTR_LAST_ANALYSIS_AT = "last_analysis_at"
ATTR_ANALYSIS_RUNNING = "analysis_running"

DANGEROUS_ACTION_ARM_TIMEOUT_SECONDS = 30
