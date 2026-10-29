"""Constants for the Broadlink AC integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "broadlink_ac"
PLATFORMS = [Platform.CLIMATE, Platform.SWITCH, Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_HOST = "host"
CONF_MAC = "mac"
CONF_PORT = "port"
CONF_NAME = "name"
CONF_POLL_INTERVAL = "poll_interval"
CONF_INVERT_DISPLAY = "invert_display"
CONF_ENABLED_SWITCHES = "enabled_switches"

SWITCH_KEYS = ("display", "health", "clean", "mildew")

DEFAULT_PORT = 80
DEFAULT_POLL_INTERVAL = 10
MIN_POLL_INTERVAL = 10
MAX_POLL_INTERVAL = 300
AMBIENT_INTERVAL = 180

HVAC_MODE_CODES = {
    0: "auto",
    1: "cool",
    2: "dry",
    4: "heat",
    6: "fan_only",
}
HVAC_MODE_TO_CODE = {value: key for key, value in HVAC_MODE_CODES.items()}

FAN_MODE_CODES = {
    0: "none",
    1: "high",
    2: "medium",
    3: "low",
    5: "auto",
}
FAN_MODE_TO_CODE = {value: key for key, value in FAN_MODE_CODES.items()}

VERTICAL_SWING_CODES = {
    0: "off",
    1: "top",
    2: "middle1",
    3: "middle2",
    4: "middle3",
    5: "bottom",
    6: "swing",
    7: "auto",
}
VERTICAL_SWING_TO_CODE = {value: key for key, value in VERTICAL_SWING_CODES.items()}

HORIZONTAL_SWING_CODES = {
    0: "left_right_flap",
    1: "left_flap",
    2: "left_fix",
    5: "right_flap",
    6: "right_fix",
    7: "left_right_fix",
}
HORIZONTAL_SWING_TO_CODE = {value: key for key, value in HORIZONTAL_SWING_CODES.items()}

FAN_MODES = ["auto", "low", "medium", "high", "turbo", "mute"]
VERTICAL_SWING_MODES = list(VERTICAL_SWING_TO_CODE)
HORIZONTAL_SWING_MODES = list(HORIZONTAL_SWING_TO_CODE)
