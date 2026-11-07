"""Home Assistant fixtures; device I/O is mocked at the protocol boundary."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.broadlink_ac.protocol.device import AcDevice
from custom_components.broadlink_ac.protocol.state import AcState

DOMAIN = "broadlink_ac"
MAC = "34:ea:34:5b:0f:d4"


@pytest.fixture(autouse=True)
def custom_integration(enable_custom_integrations):
    """Allow the integration to load in a real Home Assistant instance."""


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    (Path(hass_tmp_config_dir) / "custom_components" / DOMAIN).symlink_to(
        Path(__file__).parents[2] / "custom_components" / DOMAIN,
        target_is_directory=True,
    )
    return hass_tmp_config_dir


@pytest.fixture
def device():
    device = MagicMock(spec=AcDevice)
    device.mac = MAC
    device.host = "192.0.2.10"
    device.read_state = AsyncMock(return_value=AcState(23.5, True, 1, 5, 0, 0))
    device.read_ambient = AsyncMock(return_value=24.2)
    device.session_data.return_value = None
    with (
        patch(
            "custom_components.broadlink_ac.protocol.device.AcDevice",
            return_value=device,
        ),
        patch(
            "custom_components.broadlink_ac.config_flow.AcDevice", return_value=device
        ),
    ):
        yield device
