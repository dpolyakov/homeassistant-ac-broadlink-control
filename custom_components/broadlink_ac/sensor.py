"""Diagnostic sensors."""

from __future__ import annotations

from datetime import datetime

from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass

from . import BroadlinkAcConfigEntry
from .coordinator import BroadlinkAcCoordinator
from .entity import BroadlinkAcEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BroadlinkAcConfigEntry,
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


class BroadlinkAcBuiltInTemperatureSensor(BroadlinkAcEntity, SensorEntity):
    """Temperature reported by the device ambient sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: BroadlinkAcCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.mac}_built_in_temperature"
        self._attr_name = "Built-in temperature"

    @property
    def native_value(self) -> float | None:
        state = self.coordinator.data
        return None if state is None else state.ambient_temperature


class _DiagnosticSensor(BroadlinkAcEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: BroadlinkAcCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.mac}_{key}"
        self._attr_name = name


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

