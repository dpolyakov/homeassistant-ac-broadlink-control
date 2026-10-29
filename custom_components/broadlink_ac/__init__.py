"""Local Broadlink AUX / AC Freedom climate integration."""

from __future__ import annotations


async def async_setup(hass, config: dict) -> bool:
    """Set up the integration domain."""
    return True


async def async_setup_entry(hass, entry) -> bool:
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
    try:
        await coordinator.async_load_session()
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await device.close()
        raise
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry) -> bool:
    """Unload one Broadlink AC config entry."""
    from .const import PLATFORMS
    from .coordinator import BroadlinkAcCoordinator

    coordinator: BroadlinkAcCoordinator = entry.runtime_data
    try:
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    finally:
        await coordinator.async_shutdown()
