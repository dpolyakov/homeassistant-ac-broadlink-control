"""Exercise setup and options through Home Assistant's flow manager."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.broadlink_ac.config_flow import _local_ip
from custom_components.broadlink_ac.protocol.device import (
    AuthenticationError,
    DeviceError,
    ProtocolError,
    TransportError,
    UnsupportedDeviceError,
)
from custom_components.broadlink_ac.protocol.discovery import DiscoveredDevice

DOMAIN = "broadlink_ac"
MAC = "34:ea:34:5b:0f:d4"
DATA = {"host": "192.0.2.10", "mac": "34-EA-34-5B-0F-D4", "port": 80}
DISCOVERED = DiscoveredDevice(DATA["host"], MAC, "Bedroom AC", False, 0x4E2A)


@pytest.fixture(autouse=True)
def setup_entry():
    with patch(
        "custom_components.broadlink_ac.async_setup_entry", return_value=True
    ) as setup:
        yield setup


@pytest.fixture
def discovery():
    with (
        patch(
            "custom_components.broadlink_ac.config_flow._local_ip",
            return_value="192.0.2.1",
        ),
        patch(
            "custom_components.broadlink_ac.config_flow.async_discover",
            return_value=[DISCOVERED],
        ) as discover,
    ):
        yield discover


async def start(hass, step):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


def assert_entry(result, title):
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == title
    assert result["result"].unique_id == MAC
    assert result["data"] == {**DATA, "mac": MAC}
    assert result["options"] == {"enabled_switches": []}


async def test_manual(hass, device):
    result = await start(hass, "manual")
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert set(result["data_schema"].schema) == {"host", "mac", "port"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert_entry(result, MAC)
    device.authenticate.assert_awaited_once()
    device.read_state.assert_awaited_once()
    device.close.assert_awaited_once()
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("host", "not-an-ip", "invalid_host"),
        ("host", "::1", "invalid_host"),
        ("mac", "invalid", "invalid_mac"),
        ("mac", "aa:bb", "invalid_mac"),
    ],
)
async def test_invalid_input_then_recover(hass, device, field, value, error):
    result = await start(hass, "manual")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**DATA, field: value}
    )
    assert result["errors"] == {"base": error}
    device.authenticate.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert_entry(result, MAC)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AuthenticationError, "auth_failed"),
        (TransportError, "cannot_connect"),
        (UnsupportedDeviceError, "unsupported_device"),
        (ProtocolError, "invalid_response"),
        (DeviceError, "cannot_connect"),
    ],
)
@pytest.mark.parametrize("step", ["manual", "discovery"])
async def test_device_error_then_recover(
    hass, device, discovery, exception, error, step
):
    result = await start(hass, step)
    user_input = DATA if step == "manual" else {"device": MAC}
    device.read_state.side_effect = exception("synthetic failure")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["errors"] == {"base": error}
    device.close.assert_awaited_once()
    device.read_state.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert_entry(result, MAC if step == "manual" else DISCOVERED.name)
    assert device.close.await_count == 2
    await hass.async_block_till_done()


@pytest.mark.parametrize("step", ["manual", "discovery"])
async def test_duplicate_aborts_before_connecting(hass, device, discovery, step):
    MockConfigEntry(
        domain=DOMAIN, unique_id=MAC, data={**DATA, "mac": MAC}
    ).add_to_hass(hass)
    result = await start(hass, step)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DATA if step == "manual" else {"device": MAC}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    device.authenticate.assert_not_awaited()


async def test_discovery(hass, device, discovery):
    result = await start(hass, "discovery")
    assert result["type"] is FlowResultType.FORM
    assert set(result["data_schema"].schema) == {"device"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": MAC}
    )
    assert_entry(result, DISCOVERED.name)
    discovery.assert_awaited_once_with("192.0.2.1")
    await hass.async_block_till_done()


@pytest.mark.parametrize("failure", [[], OSError("synthetic discovery failure")])
async def test_no_devices_then_rescan_and_recover(hass, device, discovery, failure):
    discovery.side_effect = [failure, [DISCOVERED]]
    result = await start(hass, "discovery")
    assert result["errors"] == {"base": "no_devices_found"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": MAC}
    )
    assert_entry(result, DISCOVERED.name)
    assert discovery.await_count == 2
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("data", "options", "expected"),
    [
        ({}, {}, {"display", "health", "clean", "mildew"}),
        ({"enabled_switches": []}, {}, set()),
        (
            {"enabled_switches": ["clean"]},
            {"enabled_switches": ["display"]},
            {"display"},
        ),
    ],
)
async def test_options(hass, data, options, expected):
    entry = MockConfigEntry(domain=DOMAIN, data={**DATA, **data}, options=options)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"]
    defaults = schema({})
    assert {
        k.removeprefix("feature_")
        for k, v in defaults.items()
        if k.startswith("feature_") and v
    } == expected
    assert "name" not in schema.schema
    assert "poll_interval" not in schema.schema
    with patch.object(
        hass.config_entries, "async_reload", new_callable=AsyncMock
    ) as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "invert_display": True,
                "feature_display": False,
                "feature_health": True,
                "feature_clean": True,
                "feature_mildew": False,
            },
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        "invert_display": True,
        "enabled_switches": ["health", "clean"],
    }
    reload.assert_awaited_once_with(entry.entry_id)


@pytest.mark.parametrize("fails", [False, True])
def test_local_ip(fails):
    with patch("custom_components.broadlink_ac.config_flow.socket.socket") as socket:
        sock = socket.return_value.__enter__.return_value
        sock.getsockname.return_value = ("192.0.2.1", 12345)
        if fails:
            sock.connect.side_effect = OSError("no interface")
        assert _local_ip() == ("0.0.0.0" if fails else "192.0.2.1")
