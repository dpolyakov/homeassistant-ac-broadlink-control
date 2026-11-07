"""Switch entities backed by the shared full AC state."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers import entity_registry as er

from . import BroadlinkAcConfigEntry
from .const import CONF_ENABLED_SWITCHES, DOMAIN, SWITCH_KEYS
from .coordinator import BroadlinkAcCoordinator
from .entity import BroadlinkAcEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BroadlinkAcConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create only the switches selected for this device."""
    coordinator: BroadlinkAcCoordinator = entry.runtime_data
    enabled = set(
        entry.options.get(CONF_ENABLED_SWITCHES, entry.data.get(CONF_ENABLED_SWITCHES, SWITCH_KEYS))
    )
    registry = er.async_get(hass)
    for key in SWITCH_KEYS:
        if key not in enabled:
            entity_id = registry.async_get_entity_id("switch", DOMAIN, f"{coordinator.device.mac}_{key}")
            if entity_id is not None:
                registry.async_remove(entity_id)
    async_add_entities(
        [
            BroadlinkAcSwitch(coordinator, key, name)
            for key, name in (
                ("display", "Display"),
                ("health", "Health"),
                ("clean", "Clean"),
                ("mildew", "Mildew protection"),
            )
            if key in enabled
        ]
    )


class BroadlinkAcSwitch(BroadlinkAcEntity, SwitchEntity):
    """One boolean protocol state field."""

    def __init__(self, coordinator: BroadlinkAcCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device.mac}_{key}"

    @property
    def is_on(self) -> bool | None:
        state = self.coordinator.data
        if state is None:
            return None
        if self.key == "display":
            value = state.display_raw
            return not value if self.coordinator.invert_display else value
        return bool(getattr(state, self.key))

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)

    async def _set(self, enabled: bool) -> None:
        if self.key == "display":
            display_raw = enabled
            if self.coordinator.invert_display:
                display_raw = not enabled
            await self.coordinator.async_request_state_change(display_raw=display_raw)
        else:
            await self.coordinator.async_request_state_change(**{self.key: enabled})
