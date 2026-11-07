"""Shared device identity and coordinator subscriptions."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BroadlinkAcCoordinator


class BroadlinkAcEntity(CoordinatorEntity[BroadlinkAcCoordinator]):
    """An entity belonging to one locally controlled air conditioner."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Associate every platform with the same device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device.mac)},
            name=self.coordinator.device_name,
            manufacturer="AUX / Broadlink",
            model="AC Freedom / 0x4E2a",
        )
