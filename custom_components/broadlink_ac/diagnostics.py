"""Safe diagnostics for a configured device."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    """Return redacted diagnostics without raw packets or session keys."""
    coordinator = entry.runtime_data
    state = coordinator.data
    return {
        "host": "redacted",
        "mac": "redacted",
        "port": entry.data.get("port", 80),
        "available": coordinator.last_update_success,
        "last_packet": coordinator.last_packet,
        "error_count": coordinator.error_count,
        "state": None
        if state is None
        else {
            "target_temperature": state.target_temperature,
            "power": state.power,
            "mode_code": state.mode_code,
            "fan_speed_code": state.fan_speed_code,
            "vertical_swing_code": state.vertical_swing_code,
            "horizontal_swing_code": state.horizontal_swing_code,
            "ambient_temperature": state.ambient_temperature,
            "ifeel": state.ifeel,
            "fahrenheit": state.fahrenheit,
        },
    }
