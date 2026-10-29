"""Persistent session storage."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN


class AcStore:
    """Versioned storage for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict](hass, 1, f"{DOMAIN}.{entry_id}.json")

    async def async_load(self) -> dict:
        """Load persisted session data."""
        data = await self._store.async_load()
        return data if isinstance(data, dict) else {}

    async def async_save(self, data: dict) -> None:
        """Persist session data."""
        await self._store.async_save(data)
