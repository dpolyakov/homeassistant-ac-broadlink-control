"""Local Broadlink AUX / AC Freedom climate integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import BroadlinkAcCoordinator

type BroadlinkAcConfigEntry = ConfigEntry[BroadlinkAcCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration domain."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BroadlinkAcConfigEntry) -> bool:
    """Set up one Broadlink AC config entry."""
    from .const import PLATFORMS
    from .coordinator import BroadlinkAcCoordinator
    from .protocol.device import AcDevice
    from .store import AcStore

    device = AcDevice(
        host=entry.data["host"],
        mac=entry.data["mac"],
        port=entry.data["port"],
    )
    store = AcStore(hass, entry.entry_id)
    coordinator = BroadlinkAcCoordinator(hass, entry, device, store)
    await coordinator.async_load_session()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BroadlinkAcConfigEntry) -> bool:
    """Unload one Broadlink AC config entry."""
    from .const import PLATFORMS

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
