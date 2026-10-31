"""Climate entity for a Broadlink AUX air conditioner."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    FAN_MODES,
    FAN_MODE_CODES,
    HVAC_MODE_CODES,
    HVAC_MODE_TO_CODE,
    HORIZONTAL_SWING_CODES,
    HORIZONTAL_SWING_MODES,
    HORIZONTAL_SWING_TO_CODE,
    VERTICAL_SWING_CODES,
    VERTICAL_SWING_MODES,
    VERTICAL_SWING_TO_CODE,
)
from .coordinator import BroadlinkAcCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the climate entity."""
    async_add_entities([BroadlinkAcClimate(entry.runtime_data)])


class BroadlinkAcClimate(CoordinatorEntity[BroadlinkAcCoordinator], ClimateEntity):
    """Native climate representation of one device."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.COOL, HVACMode.DRY, HVACMode.HEAT, HVACMode.FAN_ONLY]
    _attr_fan_modes = FAN_MODES
    _attr_swing_modes = VERTICAL_SWING_MODES
    _attr_swing_horizontal_modes = HORIZONTAL_SWING_MODES
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.SWING_HORIZONTAL_MODE
    )

    def __init__(self, coordinator: BroadlinkAcCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.mac}_climate"
        self._attr_name = "Climate"
        self._last_hvac_mode = HVACMode.AUTO
        self._last_fan_mode = "auto"
        self._last_vertical_swing = "off"
        self._last_horizontal_swing = HORIZONTAL_SWING_MODES[0]

    @property
    def device_info(self):
        """Return device registry information."""
        from homeassistant.helpers.entity import DeviceInfo

        return DeviceInfo(
            identifiers={("broadlink_ac", self.coordinator.device.mac)},
            name=self.coordinator.name,
            manufacturer="AUX / Broadlink",
            model="AC Freedom / 0x4E2a",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def _state(self):
        return self.coordinator.data

    @property
    def temperature_unit(self) -> str:
        return self.hass.config.units.temperature_unit

    @property
    def min_temp(self) -> float:
        return self._from_celsius(16)

    @property
    def max_temp(self) -> float:
        return self._from_celsius(32)

    @property
    def target_temperature(self) -> float | None:
        state = self._state
        return None if state is None else self._from_celsius(state.target_temperature)

    @property
    def current_temperature(self) -> float | None:
        state = self._state
        if state is None or state.ambient_temperature is None:
            return None
        return self._from_celsius(state.ambient_temperature)

    @property
    def hvac_mode(self) -> str | None:
        state = self._state
        if state is None:
            return None
        if not state.power:
            return HVACMode.OFF
        mode = HVAC_MODE_CODES.get(state.mode_code, self._last_hvac_mode)
        if mode != HVACMode.OFF:
            self._last_hvac_mode = mode
        return mode

    @property
    def fan_mode(self) -> str | None:
        state = self._state
        if state is None:
            return None
        if state.mute:
            self._last_fan_mode = "mute"
        elif state.turbo:
            self._last_fan_mode = "turbo"
        else:
            fan_mode = FAN_MODE_CODES.get(state.fan_speed_code)
            if fan_mode and fan_mode != "none":
                self._last_fan_mode = fan_mode
        return self._last_fan_mode

    @property
    def swing_mode(self) -> str | None:
        state = self._state
        if state is None:
            return None
        self._last_vertical_swing = VERTICAL_SWING_CODES.get(state.vertical_swing_code, self._last_vertical_swing)
        return self._last_vertical_swing

    @property
    def swing_horizontal_mode(self) -> str | None:
        state = self._state
        if state is None:
            return None
        self._last_horizontal_swing = HORIZONTAL_SWING_CODES.get(
            state.horizontal_swing_code,
            self._last_horizontal_swing,
        )
        return self._last_horizontal_swing

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set HVAC mode and power."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_request_state_change(power=False)
            return
        if hvac_mode not in HVAC_MODE_TO_CODE:
            raise ValueError(f"unsupported HVAC mode: {hvac_mode}")
        await self.coordinator.async_request_state_change(
            power=True,
            mode_code=HVAC_MODE_TO_CODE[hvac_mode],
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        celsius = self._to_celsius(float(kwargs[ATTR_TEMPERATURE]))
        celsius = round(celsius * 2) / 2
        await self.coordinator.async_request_state_change(target_temperature=celsius)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set ordinary or special fan mode."""
        if fan_mode == "turbo":
            changes = {"turbo": True, "mute": False}
        elif fan_mode == "mute":
            changes = {"turbo": False, "mute": True}
        elif fan_mode in FAN_MODE_CODES:
            changes = {"fan_speed_code": FAN_MODE_CODES[fan_mode], "turbo": False, "mute": False}
        else:
            raise ValueError(f"unsupported fan mode: {fan_mode}")
        await self.coordinator.async_request_state_change(**changes)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set vertical swing."""
        if swing_mode not in VERTICAL_SWING_TO_CODE:
            raise ValueError(f"unsupported vertical swing mode: {swing_mode}")
        await self.coordinator.async_request_state_change(vertical_swing_code=VERTICAL_SWING_TO_CODE[swing_mode])

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set horizontal swing."""
        if swing_horizontal_mode not in HORIZONTAL_SWING_TO_CODE:
            raise ValueError(f"unsupported horizontal swing mode: {swing_horizontal_mode}")
        await self.coordinator.async_request_state_change(
            horizontal_swing_code=HORIZONTAL_SWING_TO_CODE[swing_horizontal_mode]
        )

    def _from_celsius(self, value: float) -> float:
        if self.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return value * 9 / 5 + 32
        return value

    def _to_celsius(self, value: float) -> float:
        if self.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return (value - 32) * 5 / 9
        return value
