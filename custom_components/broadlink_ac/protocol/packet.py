"""Broadlink packet and application-frame encoding."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv4Address

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = bytes.fromhex("5A A5 AA 55 5A A5 AA 55")
DEVICE_TYPE = 0x4E2A
HEADER_SIZE = 0x38
INITIAL_KEY = bytes.fromhex("09 76 28 34 3F E9 9E 23 76 5C 15 13 AC CF 8B 02")
AES_IV = bytes.fromhex("56 2E 17 99 6D 09 3D 28 DD B3 BA 69 5A 2E 6F 58")


class PacketError(ValueError):
    """Raised when a packet or application frame is malformed."""


class UnsupportedPacketError(PacketError):
    """Raised when a response belongs to another device type."""


@dataclass(frozen=True, slots=True)
class ParsedPacket:
    """Decoded Broadlink packet metadata and plaintext payload."""

    command: int
    sequence: int
    error: int
    payload: bytes


def broadlink_checksum(data: bytes | bytearray) -> int:
    """Return the Broadlink additive checksum."""
    return (0xBEAF + sum(data)) & 0xFFFF


def ones_complement_checksum(data: bytes | bytearray) -> int:
    """Return the application-frame checksum."""
    total = sum(
        (data[index] << 8) | (data[index + 1] if index + 1 < len(data) else 0)
        for index in range(0, len(data), 2)
    )
    total = ((total >> 16) + (total & 0xFFFF)) & 0xFFFF
    return (~total) & 0xFFFF


def _pad_zero(data: bytes) -> bytes:
    """Pad data with zero bytes to an AES block boundary."""
    padding = (-len(data)) % 16
    return data + (b"\0" * padding)


def encrypt_payload(payload: bytes, key: bytes) -> bytes:
    """Encrypt an already block-aligned payload."""
    if len(payload) % 16:
        raise PacketError("payload must be AES block aligned")
    cipher = Cipher(algorithms.AES(key), modes.CBC(AES_IV))
    encryptor = cipher.encryptor()
    return encryptor.update(payload) + encryptor.finalize()


def decrypt_payload(payload: bytes, key: bytes) -> bytes:
    """Decrypt an already block-aligned payload."""
    if len(payload) % 16:
        raise PacketError("encrypted payload must be AES block aligned")
    cipher = Cipher(algorithms.AES(key), modes.CBC(AES_IV))
    decryptor = cipher.decryptor()
    return decryptor.update(payload) + decryptor.finalize()


def build_application_frame(data: bytes) -> bytes:
    """Build and zero-pad an application frame."""
    if not data or len(data) > 0xFD:
        raise PacketError("application data has an invalid length")
    frame = bytearray((len(data) + 2, 0))
    frame.extend(data)
    frame.extend(ones_complement_checksum(data).to_bytes(2, "big"))
    return _pad_zero(bytes(frame))


def build_get_frame(data: bytes) -> bytes:
    """Build the zero-checksum frame used by AUX GET requests."""
    if not data or len(data) > 0xFF:
        raise PacketError("GET data has an invalid length")
    frame = bytearray((len(data), 0))
    frame.extend(data)
    frame.extend(b"\0\0")
    return _pad_zero(bytes(frame))


def parse_application_frame(frame: bytes) -> bytes:
    """Validate and extract data from an application frame."""
    validate_application_frame(frame)
    data_length = frame[0] - 2
    return frame[2:2 + data_length]


def validate_application_frame(frame: bytes) -> None:
    """Validate an application frame without discarding its result header."""
    if len(frame) < 4 or frame[1] != 0:
        raise PacketError("invalid application frame header")
    data_length = frame[0] - 2
    if data_length < 1 or data_length + 4 > len(frame):
        raise PacketError("invalid application frame length")
    data_start = 2
    checksum_start = data_start + data_length
    data = frame[data_start:checksum_start]
    expected = int.from_bytes(frame[checksum_start:checksum_start + 2], "big")
    if ones_complement_checksum(data) != expected:
        raise PacketError("application checksum is incorrect")


def build_packet(
    command: int,
    sequence: int,
    mac: bytes,
    device_id: bytes,
    plaintext_payload: bytes,
    key: bytes,
) -> bytes:
    """Build a Broadlink UDP packet."""
    if len(mac) != 6 or len(device_id) != 4:
        raise PacketError("MAC or device id has an invalid length")
    plaintext_payload = _pad_zero(plaintext_payload)
    encrypted = encrypt_payload(plaintext_payload, key)
    packet = bytearray(HEADER_SIZE + len(encrypted))
    packet[0:8] = MAGIC
    packet[0x24:0x26] = DEVICE_TYPE.to_bytes(2, "little")
    packet[0x26] = command
    packet[0x28:0x2A] = (sequence & 0xFFFF).to_bytes(2, "little")
    packet[0x2A:0x30] = mac
    packet[0x30:0x34] = device_id
    packet[0x34:0x36] = broadlink_checksum(plaintext_payload).to_bytes(2, "little")
    packet[HEADER_SIZE:] = encrypted
    packet[0x20:0x22] = b"\0\0"
    packet[0x20:0x22] = broadlink_checksum(packet).to_bytes(2, "little")
    return bytes(packet)


def parse_packet(packet: bytes, key: bytes) -> ParsedPacket:
    """Validate a response and decrypt its payload."""
    if len(packet) < HEADER_SIZE or packet[:8] != MAGIC:
        raise PacketError("invalid Broadlink packet header")
    if int.from_bytes(packet[0x24:0x26], "little") != DEVICE_TYPE:
        raise UnsupportedPacketError("unsupported Broadlink device type")
    packet_for_checksum = bytearray(packet)
    received_checksum = int.from_bytes(packet[0x20:0x22], "little")
    packet_for_checksum[0x20:0x22] = b"\0\0"
    if broadlink_checksum(packet_for_checksum) != received_checksum:
        raise PacketError("Broadlink checksum is incorrect")
    encrypted = packet[HEADER_SIZE:]
    plaintext = decrypt_payload(encrypted, key)
    payload_checksum = int.from_bytes(packet[0x34:0x36], "little")
    if error := int.from_bytes(packet[0x22:0x24], "little"):
        return ParsedPacket(
            command=packet[0x26],
            sequence=int.from_bytes(packet[0x28:0x2A], "little"),
            error=error,
            payload=plaintext,
        )
    if broadlink_checksum(plaintext) != payload_checksum:
        raise PacketError("payload checksum is incorrect")
    return ParsedPacket(
        command=packet[0x26],
        sequence=int.from_bytes(packet[0x28:0x2A], "little"),
        error=0,
        payload=plaintext,
    )


def build_auth_payload() -> bytes:
    """Build the documented authentication payload."""
    payload = bytearray(0x50)
    payload[0x04:0x13] = b"1" * 15
    payload[0x1E] = 0x01
    payload[0x2D] = 0x01
    payload[0x30:0x37] = b"Test  1"
    return bytes(payload)


def build_discovery_packet(
    local_ip: str,
    local_port: int,
    *,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    hour: int | None = None,
    minute: int | None = None,
    weekday: int | None = None,
    utc_offset_seconds: int | None = None,
) -> bytes:
    """Build the 48-byte local discovery packet."""
    now = datetime.now().astimezone()
    year = now.year if year is None else year
    month = now.month if month is None else month
    day = now.day if day is None else day
    hour = now.hour if hour is None else hour
    minute = now.minute if minute is None else minute
    weekday = now.isoweekday() if weekday is None else weekday
    utc_offset_seconds = int(now.utcoffset().total_seconds()) if utc_offset_seconds is None else utc_offset_seconds
    timezone_hours = int(utc_offset_seconds / 3600)
    packet = bytearray(0x30)
    if timezone_hours < 0:
        packet[0x08] = (0x100 + timezone_hours) & 0xFF
        packet[0x09:0x0C] = b"\xff\xff\xff"
    else:
        packet[0x08] = timezone_hours & 0xFF
    packet[0x0C:0x0E] = year.to_bytes(2, "little")
    packet[0x0E:0x14] = bytes((minute, hour, year % 100, weekday, day, month))
    packet[0x18:0x1C] = IPv4Address(local_ip).packed
    packet[0x1C:0x1E] = local_port.to_bytes(2, "little")
    packet[0x26] = 6
    packet[0x20:0x22] = broadlink_checksum(packet).to_bytes(2, "little")
    return bytes(packet)
