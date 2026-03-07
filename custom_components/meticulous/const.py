"""Constants for the Meticulous integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "meticulous"

CONF_TOKEN = "token"
DEFAULT_PORT = 8080

COORDINATOR_UPDATE_INTERVAL = timedelta(seconds=5)

PLATFORMS: list[str] = ["sensor", "binary_sensor", "button", "switch"]

ATTR_TEMPERATURE = "temperature"
ATTR_PRESSURE = "pressure"
ATTR_FLOW_RATE = "flow_rate"
ATTR_SCALE_WEIGHT = "scale_weight"
ATTR_MOTOR_LOAD = "motor_load"
ATTR_BREW_STATE = "brew_state"
ATTR_WATER_TEMP = "water_temp"
ATTR_AUTO_PURGE = "auto_purge"

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
