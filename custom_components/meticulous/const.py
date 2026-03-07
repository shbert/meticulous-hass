"""Constants for the Meticulous integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "meticulous"

CONF_TOKEN = "token"
DEFAULT_PORT = 8080

COORDINATOR_UPDATE_INTERVAL = timedelta(seconds=5)

PLATFORMS: list[str] = ["sensor", "button"]

ATTR_TEMPERATURE = "temperature"
ATTR_PRESSURE = "pressure"
ATTR_FLOW_RATE = "flow_rate"
ATTR_SCALE_WEIGHT = "scale_weight"
ATTR_MOTOR_LOAD = "motor_load"
ATTR_BREW_STATE = "brew_state"
ATTR_WATER_TEMP = "water_temp"
