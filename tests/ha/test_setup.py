"""Verify first refresh, entity identity, and coordinator subscriptions in HA."""

from datetime import timedelta
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.broadlink_ac.const import DOMAIN
from custom_components.broadlink_ac.protocol.device import UnsupportedDeviceError

MAC = "34:ea:34:5b:0f:d4"


def make_entry(hass, *, switches=()):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bedroom AC",
        unique_id=MAC,
        data={"host": "192.0.2.10", "mac": MAC, "port": 80},
        options={"enabled_switches": list(switches), "poll_interval": 300},
    )
    entry.add_to_hass(hass)
    return entry


async def test_setup_entities_and_unload(hass, device):
    entry = make_entry(hass, switches=("display", "health", "clean", "mildew"))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    coordinator = entry.runtime_data
    assert coordinator.device is device
    assert coordinator.update_interval == timedelta(seconds=10)
    assert coordinator.data.ambient_temperature == 24.2
    device.read_state.assert_awaited_once()
    device.read_ambient.assert_awaited_once()
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 9
    assert {entity.domain for entity in entities} == {
        "climate",
        "sensor",
        "switch",
        "binary_sensor",
    }
    assert len({entity.unique_id for entity in entities}) == 9
    device_entry = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, MAC), entry.entry_id
    )
    assert device_entry is not None
    assert {entity.device_id for entity in entities} == {device_entry.id}
    climate_id = registry.async_get_entity_id("climate", DOMAIN, f"{MAC}_climate")
    assert hass.states.get(climate_id).attributes["friendly_name"] == "Bedroom AC"
    assert hass.states.get(climate_id).attributes["current_temperature"] == 24.2
    assert coordinator._listeners
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not coordinator._listeners
    device.close.assert_awaited_once()


async def test_first_refresh_failure_does_not_create_entities(hass, device):
    entry = make_entry(hass)
    device.read_state.side_effect = UnsupportedDeviceError(
        "synthetic unsupported device"
    )
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    device.close.assert_awaited_once()


async def test_selected_switches_reload_without_duplicate_entities(hass, device):
    entry = make_entry(hass, switches=("display",))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    display_id = registry.async_get_entity_id("switch", DOMAIN, f"{MAC}_display")
    assert display_id is not None
    old_coordinator = entry.runtime_data
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "invert_display": True,
            "feature_clean": True,
            "feature_display": False,
        },
    )
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not old_coordinator
    assert not old_coordinator._listeners
    assert entry.runtime_data.invert_display is True
    assert registry.async_get_entity_id("switch", DOMAIN, f"{MAC}_display") is None
    assert registry.async_get_entity_id("switch", DOMAIN, f"{MAC}_clean") is not None
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 6
    device.close.assert_awaited_once()
    assert await hass.config_entries.async_unload(entry.entry_id)
