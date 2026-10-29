"""Config and options flows."""

from __future__ import annotations

import asyncio
import ipaddress
import socket

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback

from .const import (
    CONF_INVERT_DISPLAY,
    CONF_MAC,
    CONF_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)
from .protocol.device import (
    AcDevice,
    AuthenticationError,
    DeviceError,
    ProtocolError,
    TransportError,
    UnsupportedDeviceError,
)
from .protocol.discovery import async_discover, normalize_mac


def _local_ip() -> str:
    """Best-effort local IPv4 address for discovery."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("255.255.255.255", 80))
            return sock.getsockname()[0]
    except OSError:
        return "0.0.0.0"


class BroadlinkAcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Broadlink AC setup."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Choose manual or discovery setup."""
        return self.async_show_menu(step_id="user", menu_options=["manual", "discovery"])

    async def async_step_manual(self, user_input=None):
        """Configure a device manually."""
        errors = {}
        if user_input is not None:
            result = await self._try_device(user_input)
            if result is None:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or user_input[CONF_MAC],
                    data=user_input,
                )
            errors["base"] = result
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_MAC): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Optional(CONF_NAME, default=""): str,
            }
        )
        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)

    async def async_step_discovery(self, user_input=None):
        """Discover compatible devices explicitly."""
        if not hasattr(self, "_discovered"):
            try:
                self._discovered = await async_discover(await asyncio.to_thread(_local_ip))
            except OSError:
                self._discovered = []
        if user_input is not None:
            selected = next(item for item in self._discovered if item.mac == user_input["device"])
            data = {
                CONF_HOST: selected.host,
                CONF_MAC: selected.mac,
                CONF_PORT: DEFAULT_PORT,
                CONF_NAME: user_input.get(CONF_NAME) or selected.name,
            }
            error = await self._try_device(data)
            if error is None:
                return self.async_create_entry(title=data[CONF_NAME], data=data)
            return self.async_show_form(
                step_id="discovery",
                data_schema=self._discovery_schema(),
                errors={"base": error},
            )
        if not self._discovered:
            return self.async_show_form(
                step_id="discovery",
                data_schema=vol.Schema({}),
                errors={"base": "no_devices_found"},
            )
        return self.async_show_form(step_id="discovery", data_schema=self._discovery_schema())

    def _discovery_schema(self):
        """Build the discovered-device selector."""
        return vol.Schema(
            {
                vol.Required("device"): vol.In({item.mac: item.name for item in self._discovered}),
                vol.Optional(CONF_NAME, default=""): str,
            }
        )

    async def _try_device(self, data: dict) -> str | None:
        """Test connectivity and reject duplicate MAC entries."""
        try:
            ipaddress.IPv4Address(data[CONF_HOST])
        except ipaddress.AddressValueError:
            return "invalid_host"
        try:
            mac = normalize_mac(data[CONF_MAC])
        except ValueError:
            return "invalid_mac"
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()
        device = AcDevice(data[CONF_HOST], mac, data.get(CONF_PORT, DEFAULT_PORT))
        try:
            await device.authenticate()
            await device.read_state()
        except AuthenticationError:
            return "auth_failed"
        except TransportError:
            return "cannot_connect"
        except UnsupportedDeviceError:
            return "unsupported_device"
        except ProtocolError:
            return "invalid_response"
        except DeviceError:
            return "cannot_connect"
        finally:
            await device.close()
        data[CONF_MAC] = mac
        return None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return BroadlinkAcOptionsFlow(config_entry)


class BroadlinkAcOptionsFlow(config_entries.OptionsFlow):
    """Handle options for a configured device."""

    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Edit name, poll interval, and display inversion."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=self.config_entry.options.get(CONF_NAME, self.config_entry.data.get(CONF_NAME, ""))): str,
                vol.Required(
                    CONF_POLL_INTERVAL,
                    default=self.config_entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL)),
                vol.Required(CONF_INVERT_DISPLAY, default=self.config_entry.options.get(CONF_INVERT_DISPLAY, False)): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
