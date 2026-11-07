"""Read-only binary sensors for a Broadlink AC."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BroadlinkAcConfigEntry
from .coordinator import BroadlinkAcCoordinator
from .entity import BroadlinkAcEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BroadlinkAcConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create read-only binary sensors."""
    async_add_entities([BroadlinkAcIFeelBinarySensor(entry.runtime_data)])


class BroadlinkAcIFeelBinarySensor(BroadlinkAcEntity, BinarySensorEntity):
    """Whether iFeel is currently enabled on the air conditioner."""

    _attr_icon = "mdi:remote"

    def __init__(self, coordinator: BroadlinkAcCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.mac}_ifeel"
        self._attr_name = "I-feel"

    @property
    def is_on(self) -> bool | None:
        state = self.coordinator.data
        return None if state is None else state.ifeel
