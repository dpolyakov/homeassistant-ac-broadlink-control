"""Read-only binary sensors for a Broadlink AC."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import BroadlinkAcCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create read-only binary sensors."""
    async_add_entities([BroadlinkAcIFeelBinarySensor(entry.runtime_data)])


class BroadlinkAcIFeelBinarySensor(BinarySensorEntity):
    """Whether iFeel is currently enabled on the air conditioner."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:remote"

    def __init__(self, coordinator: BroadlinkAcCoordinator) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.device.mac}_ifeel"
        self._attr_name = "I-feel"

    @property
    def device_info(self):
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
    def is_on(self) -> bool | None:
        state = self.coordinator.data
        return None if state is None else state.ifeel
