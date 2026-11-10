"""Exercise climate capabilities through Home Assistant services."""

from dataclasses import replace

import pytest
from homeassistant.components.climate.const import ClimateEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.broadlink_ac.const import DOMAIN


@pytest.fixture
async def climate(hass, device):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bedroom AC",
        unique_id=device.mac,
        data={"host": device.host, "mac": device.mac, "port": 80},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "climate", DOMAIN, f"{device.mac}_climate"
    )

    async def apply_state(state):
        device.read_state.return_value = state

    device.apply_state.side_effect = apply_state
    yield entry.runtime_data, entity_id
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("fan_mode", "changes"),
    [
        ("auto", {"fan_speed_code": 5, "turbo": False, "mute": False}),
        ("low", {"fan_speed_code": 3, "turbo": False, "mute": False}),
        ("medium", {"fan_speed_code": 2, "turbo": False, "mute": False}),
        ("high", {"fan_speed_code": 1, "turbo": False, "mute": False}),
        ("turbo", {"turbo": True, "mute": False}),
        ("mute", {"turbo": False, "mute": True}),
    ],
)
async def test_fan_modes(hass, device, climate, fan_mode, changes):
    coordinator, entity_id = climate
    previous = replace(coordinator.data, turbo=True, mute=True)
    coordinator.async_set_updated_data(previous)
    await hass.async_block_till_done()
    attributes = hass.states.get(entity_id).attributes
    assert attributes["supported_features"] & ClimateEntityFeature.FAN_MODE
    assert attributes["fan_modes"] == ["auto", "low", "medium", "high", "turbo", "mute"]

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": entity_id, "fan_mode": fan_mode},
        blocking=True,
    )

    device.apply_state.assert_awaited_once_with(replace(previous, **changes))
    assert hass.states.get(entity_id).attributes["fan_mode"] == fan_mode


async def test_unknown_fan_mode_does_not_send(hass, device, climate):
    _, entity_id = climate
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_fan_mode",
            {"entity_id": entity_id, "fan_mode": "unknown"},
            blocking=True,
        )
    device.apply_state.assert_not_awaited()


@pytest.mark.parametrize("power", [True, False])
async def test_power_preserves_settings(hass, device, climate, power):
    coordinator, entity_id = climate
    previous = replace(
        coordinator.data,
        power=not power,
        mode_code=1,
        target_temperature=22.5,
        fan_speed_code=3,
        turbo=True,
        vertical_swing_code=6,
        horizontal_swing_code=5,
    )
    coordinator.async_set_updated_data(previous)
    await hass.async_block_till_done()
    features = hass.states.get(entity_id).attributes["supported_features"]
    assert features & ClimateEntityFeature.TURN_ON
    assert features & ClimateEntityFeature.TURN_OFF

    await hass.services.async_call(
        "climate",
        "turn_on" if power else "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    device.apply_state.assert_awaited_once_with(replace(previous, power=power))
    assert hass.states.get(entity_id).state == ("cool" if power else "off")
