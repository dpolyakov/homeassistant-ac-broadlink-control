"""Local UDP discovery for Broadlink AUX air conditioners."""

from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass

from .packet import DEVICE_TYPE, PacketError, build_discovery_packet


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    """A device returned by the Broadlink discovery response."""

    host: str
    mac: str
    name: str
    cloud_bound: bool
    devtype: int


def normalize_mac(mac: str | bytes) -> str:
    """Return a lowercase colon-separated MAC address."""
    if isinstance(mac, bytes):
        raw = mac
    else:
        raw = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    if len(raw) != 6:
        raise ValueError("MAC address must contain six bytes")
    return ":".join(f"{value:02x}" for value in raw)


def parse_discovery_response(packet: bytes, host: str) -> DiscoveredDevice | None:
    """Parse a discovery datagram, ignoring unsupported device types."""
    if len(packet) < 0x40:
        raise PacketError("discovery response is too short")
    devtype = int.from_bytes(packet[0x34:0x36], "little")
    if devtype != DEVICE_TYPE:
        return None
    mac = normalize_mac(packet[0x3A:0x40][::-1])
    name_bytes = packet[0x40:-1].split(b"\0", 1)[0]
    try:
        name = name_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        name = ""
    return DiscoveredDevice(
        host=host,
        mac=mac,
        name=name or mac,
        cloud_bound=bool(packet[-1]),
        devtype=devtype,
    )


class _DiscoveryProtocol(asyncio.DatagramProtocol):
    """Collect broadcast discovery responses."""

    def __init__(self) -> None:
        self.responses: asyncio.Queue[tuple[bytes, tuple[str, int]]] = asyncio.Queue()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.responses.put_nowait((data, addr))


async def async_discover(local_ip: str, timeout: float = 3.0) -> list[DiscoveredDevice]:
    """Broadcast a discovery packet and return compatible devices."""
    loop = asyncio.get_running_loop()
    protocol = _DiscoveryProtocol()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: protocol,
        local_addr=(local_ip, 0),
        family=socket.AF_INET,
        allow_broadcast=True,
    )
    try:
        local_port = transport.get_extra_info("sockname")[1]
        packet = build_discovery_packet(local_ip, local_port)
        transport.sendto(packet, ("255.255.255.255", 80))
        devices: dict[str, DiscoveredDevice] = {}
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                response, addr = await asyncio.wait_for(protocol.responses.get(), remaining)
            except asyncio.TimeoutError:
                break
            try:
                device = parse_discovery_response(response, addr[0])
            except PacketError:
                continue
            if device is not None:
                devices[device.mac] = device
        return list(devices.values())
    finally:
        transport.close()
