"""Diagnostic sensors."""

from __future__ import annotations

from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass

from .coordinator import BroadlinkAcCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create diagnostic sensors."""
    coordinator: BroadlinkAcCoordinator = entry.runtime_data
    async_add_entities(
        [
            BroadlinkAcBuiltInTemperatureSensor(coordinator),
            BroadlinkAcLastPacketSensor(coordinator),
            BroadlinkAcErrorSensor(coordinator),
        ]
    )


class BroadlinkAcBuiltInTemperatureSensor(SensorEntity):
    """Temperature reported by the device ambient sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: BroadlinkAcCoordinator) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.device.mac}_built_in_temperature"
        self._attr_name = "Built-in temperature"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> float | None:
        state = self.coordinator.data
        return None if state is None else state.ambient_temperature

    @property
    def device_info(self):
        from homeassistant.helpers.entity import DeviceInfo

        return DeviceInfo(
            identifiers={("broadlink_ac", self.coordinator.device.mac)},
            name=self.coordinator.name,
            manufacturer="AUX / Broadlink",
            model="AC Freedom / 0x4E2a",
        )


class _DiagnosticSensor(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, coordinator: BroadlinkAcCoordinator, key: str, name: str) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.device.mac}_{key}"
        self._attr_name = name

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        from homeassistant.helpers.entity import DeviceInfo

        return DeviceInfo(
            identifiers={("broadlink_ac", self.coordinator.device.mac)},
            name=self.coordinator.name,
            manufacturer="AUX / Broadlink",
            model="AC Freedom / 0x4E2a",
        )


class BroadlinkAcLastPacketSensor(_DiagnosticSensor):
    """Last successful packet timestamp."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: BroadlinkAcCoordinator) -> None:
        super().__init__(coordinator, "last_packet", "Last packet")

    @property
    def native_value(self):
        value = self.coordinator.last_packet
        return None if value is None else datetime.fromtimestamp(value).astimezone()


class BroadlinkAcErrorSensor(_DiagnosticSensor):
    """Count of failed device operations."""

    def __init__(self, coordinator: BroadlinkAcCoordinator) -> None:
        super().__init__(coordinator, "errors", "Errors")

    @property
    def native_value(self) -> int:
        return self.coordinator.error_count

