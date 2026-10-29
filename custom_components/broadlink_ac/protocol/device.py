"""Async local UDP device client for the AUX air-conditioner protocol."""

from __future__ import annotations

import asyncio
import logging
import secrets
import time

from .discovery import normalize_mac
from .packet import (
    INITIAL_KEY,
    PacketError,
    build_application_frame,
    build_auth_payload,
    build_packet,
    build_get_frame,
    parse_packet,
    validate_application_frame,
    UnsupportedPacketError,
)
from .state import AcState, build_set_frame, parse_ambient_response, parse_state_response

GET_STATES = bytes.fromhex("BB 00 06 80 00 00 02 00 11 01 2B 7E")
GET_AMBIENT = bytes.fromhex("BB 00 06 80 00 00 02 00 21 01 1B 7E")

_LOGGER = logging.getLogger(__name__)


class DeviceError(Exception):
    """Base error for device communication."""


class TransportError(DeviceError):
    """The device did not respond in time or the socket failed."""


class ProtocolError(DeviceError):
    """The device returned a malformed or inconsistent response."""


class AuthenticationError(ProtocolError):
    """The device rejected the current session."""


class UnsupportedDeviceError(ProtocolError):
    """The device does not expose the supported Broadlink device type."""


class _DatagramProtocol(asyncio.DatagramProtocol):
    """Collect datagrams for one device socket."""

    def __init__(self) -> None:
        self.packets: asyncio.Queue[tuple[bytes, tuple[str, int]]] = asyncio.Queue()
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.packets.put_nowait((data, addr))

    def error_received(self, exc: Exception) -> None:
        self.packets.put_nowait((b"", ("", 0)))


class AcDevice:
    """Serialize local protocol requests to one physical device."""

    def __init__(self, host: str, mac: str, port: int = 80) -> None:
        self.host = host
        self.mac = normalize_mac(mac)
        self.port = port
        self._mac_bytes = bytes.fromhex(self.mac.replace(":", ""))
        self.device_id: bytes | None = None
        self.device_key: bytes | None = None
        self.sequence = secrets.randbelow(0xFFFF)
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _DatagramProtocol | None = None
        self._request_lock = asyncio.Lock()
        self._last_sent = 0.0

    @property
    def has_session(self) -> bool:
        """Whether a persisted or authenticated session is available."""
        return self.device_id is not None and self.device_key is not None

    def load_session(self, device_id: bytes, device_key: bytes, sequence: int = 0) -> None:
        """Load persisted session data."""
        if len(device_id) != 4 or len(device_key) != 16:
            raise ValueError("invalid persisted session data")
        self.device_id = device_id
        self.device_key = device_key
        self.sequence = sequence & 0xFFFF

    def session_data(self) -> dict[str, str | int] | None:
        """Return serializable session data."""
        if not self.has_session:
            return None
        return {
            "device_id": self.device_id.hex(),
            "device_key": self.device_key.hex(),
            "sequence": self.sequence,
        }

    def invalidate_session(self) -> None:
        """Forget the in-memory session without changing persisted storage."""
        self.device_id = None
        self.device_key = None

    async def close(self) -> None:
        """Close the device socket."""
        if self._transport is not None:
            self._transport.close()
        self._transport = None
        self._protocol = None

    async def _ensure_socket(self) -> _DatagramProtocol:
        if self._protocol is not None and self._transport is not None:
            return self._protocol
        loop = asyncio.get_running_loop()
        protocol = _DatagramProtocol()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: protocol,
            local_addr=("0.0.0.0", 0),
        )
        self._transport = transport
        self._protocol = protocol
        return protocol

    async def _wait_rate_limit(self) -> None:
        delay = 0.5 - (time.monotonic() - self._last_sent)
        if delay > 0:
            await asyncio.sleep(delay)

    def _next_sequence(self) -> int:
        self.sequence = (self.sequence + 1) & 0xFFFF
        return self.sequence

    async def _request(self, command: int, payload: bytes, key: bytes, timeout: float = 1.0):
        async with self._request_lock:
            protocol = await self._ensure_socket()
            await self._wait_rate_limit()
            sequence = self._next_sequence()
            device_id = self.device_id or b"\0\0\0\0"
            packet = build_packet(command, sequence, self._mac_bytes, device_id, payload, key)
            assert self._transport is not None
            _LOGGER.debug("UDP TX %s:%s %s", self.host, self.port, packet.hex(" "))
            try:
                self._transport.sendto(packet, (self.host, self.port))
            except OSError as err:
                raise TransportError(f"could not send to {self.host}") from err
            self._last_sent = time.monotonic()
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TransportError(f"no response from {self.host}")
                try:
                    response, addr = await asyncio.wait_for(protocol.packets.get(), remaining)
                except asyncio.TimeoutError as err:
                    raise TransportError(f"no response from {self.host}") from err
                if not response or addr[0] != self.host:
                    continue
                _LOGGER.debug("UDP RX %s:%s %s", addr[0], addr[1], response.hex(" "))
                try:
                    parsed = parse_packet(response, key)
                except UnsupportedPacketError as err:
                    raise UnsupportedDeviceError(str(err)) from err
                except PacketError as err:
                    raise ProtocolError(str(err)) from err
                if parsed.error:
                    raise AuthenticationError(f"device returned error 0x{parsed.error:04x}")
                return parsed

    async def authenticate(self) -> dict[str, str | int]:
        """Authenticate and return the new session data."""
        parsed = await self._request(0x65, build_auth_payload(), INITIAL_KEY)
        if len(parsed.payload) < 20:
            raise AuthenticationError("authentication response is too short")
        self.device_id = parsed.payload[0:4]
        self.device_key = parsed.payload[4:20]
        return self.session_data() or {}

    async def _session_request(self, payload: bytes):
        if not self.has_session:
            await self.authenticate()
        assert self.device_key is not None
        return await self._request(0x6A, payload, self.device_key)

    async def read_state(self) -> AcState:
        """Read the main device state."""
        parsed = await self._session_request(build_get_frame(GET_STATES))
        try:
            validate_application_frame(parsed.payload)
            state = parse_state_response(parsed.payload)
            _LOGGER.debug(
                "STATE response ifeel=%s fahrenheit=%s power=%s mode=%s "
                "target_temperature=%s payload=%s",
                state.ifeel,
                state.fahrenheit,
                state.power,
                state.mode_code,
                state.target_temperature,
                parsed.payload.hex(" "),
            )
            return state
        except PacketError as err:
            raise ProtocolError(str(err)) from err

    async def read_ambient(self) -> float | None:
        """Read the ambient temperature."""
        parsed = await self._session_request(build_get_frame(GET_AMBIENT))
        try:
            validate_application_frame(parsed.payload)
            ambient = parse_ambient_response(parsed.payload)
            _LOGGER.debug(
                "AMBIENT response temperature=%s payload=%s",
                ambient,
                parsed.payload.hex(" "),
            )
            return ambient
        except PacketError as err:
            raise ProtocolError(str(err)) from err

    async def apply_state(self, state: AcState) -> None:
        """Send a complete device state."""
        frame = build_set_frame(state)
        _LOGGER.debug(
            "SET request ifeel=%s fahrenheit=%s power=%s mode=%s target_temperature=%s frame=%s",
            state.ifeel,
            state.fahrenheit,
            state.power,
            state.mode_code,
            state.target_temperature,
            frame.hex(" "),
        )
        parsed = await self._session_request(frame)
        try:
            validate_application_frame(parsed.payload)
            _LOGGER.debug(
                "SET response ifeel=%s payload=%s",
                state.ifeel,
                parsed.payload.hex(" "),
            )
        except PacketError as err:
            raise ProtocolError(str(err)) from err
