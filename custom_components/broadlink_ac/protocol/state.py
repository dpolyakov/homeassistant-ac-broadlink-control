"""AUX application state parsing and full-state encoding."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .packet import PacketError, build_application_frame


@dataclass(frozen=True, slots=True)
class AcState:
    """Raw protocol state with device-independent field names."""

    target_temperature: float
    power: bool
    mode_code: int
    fan_speed_code: int
    vertical_swing_code: int
    horizontal_swing_code: int
    sleep: bool = False
    display_raw: bool = False
    mildew: bool = False
    health: bool = False
    clean: bool = False
    ifeel: bool = False
    turbo: bool = False
    mute: bool = False
    ambient_temperature: float | None = None

    def with_ambient(self, ambient_temperature: float | None) -> "AcState":
        """Return this state with a refreshed ambient value."""
        return replace(self, ambient_temperature=ambient_temperature)


def parse_state_response(response: bytes) -> AcState:
    """Parse the documented 0x19 result packet."""
    if len(response) < 25 or response[0] != 0x19 or response[4] != 0x07:
        raise PacketError("invalid state result packet")
    data = response[2:25]
    target_temperature = 8 + (data[10] >> 3) + (0.5 if data[12] & 0x80 else 0)
    if target_temperature < 16:
        raise PacketError("state temperature is invalid")
    return AcState(
        target_temperature=target_temperature,
        power=bool((data[18] >> 5) & 1),
        mode_code=(data[15] >> 5) & 0x0F,
        fan_speed_code=(data[13] >> 5) & 0x07,
        vertical_swing_code=data[10] & 0x07,
        horizontal_swing_code=(data[11] >> 5) & 0x07,
        sleep=bool((data[15] >> 2) & 1),
        display_raw=bool((data[20] >> 4) & 1),
        mildew=bool((data[20] >> 3) & 1),
        health=bool((data[18] >> 1) & 1),
        clean=bool((data[18] >> 2) & 1),
        ifeel=bool((data[15] >> 3) & 1),
        turbo=bool((data[14] >> 6) & 1),
        mute=bool((data[14] >> 7) & 1),
    )


def parse_ambient_response(response: bytes) -> float | None:
    """Parse the ambient response using the sensor-presence bit."""
    if len(response) < 40:
        raise PacketError("ambient result packet is too short")
    data = response[2:]
    raw = data[15]
    if not raw & 0x20:
        return None
    return (raw & 0x1F) + (data[31] / 10)


def build_set_data(state: AcState) -> bytes:
    """Build the complete 23-byte SET data block."""
    whole_temperature = int(state.target_temperature)
    if whole_temperature < 16 or whole_temperature > 32:
        raise ValueError("target temperature must be between 16 and 32 Celsius")
    if abs((state.target_temperature * 2) - round(state.target_temperature * 2)) > 1e-6:
        raise ValueError("target temperature must use 0.5 Celsius increments")
    half_degree = round((state.target_temperature - whole_temperature) * 2) == 1
    fan_speed = 0 if state.turbo or state.mute else state.fan_speed_code
    data = bytearray(23)
    data[0:10] = bytes.fromhex("BB 00 06 80 00 00 0F 00 01 01")
    data[10] = ((whole_temperature - 8) << 3) | (state.vertical_swing_code & 0x07)
    data[11] = (state.horizontal_swing_code & 0x07) << 5
    data[12] = 0x0F | (0x80 if half_degree else 0)
    data[13] = (fan_speed & 0x07) << 5
    data[14] = (0x40 if state.turbo else 0) | (0x80 if state.mute else 0)
    data[15] = ((state.mode_code & 0x0F) << 5) | (0x04 if state.sleep else 0)
    data[18] = (0x20 if state.power else 0) | (0x02 if state.health else 0) | (0x04 if state.clean else 0)
    data[20] = (0x10 if state.display_raw else 0) | (0x08 if state.mildew else 0)
    return bytes(data)


def build_set_frame(state: AcState) -> bytes:
    """Build the padded application SET frame."""
    return build_application_frame(build_set_data(state))
