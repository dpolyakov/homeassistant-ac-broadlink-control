import asyncio
import unittest
from unittest.mock import patch

from custom_components.broadlink_ac.protocol.device import AcDevice
from custom_components.broadlink_ac.protocol.packet import (
    INITIAL_KEY,
    build_application_frame,
    build_packet,
    parse_packet,
)


MAC = "34:ea:34:5b:0f:d4"
MAC_BYTES = bytes.fromhex("34 EA 34 5B 0F D4")
DEVICE_ID = bytes.fromhex("01 02 03 04")
SESSION_KEY = bytes.fromhex("10 11 12 13 14 15 16 17 18 19 1A 1B 1C 1D 1E 1F")


class FakeDeviceProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport = None
        self.requests = []

    def connection_made(self, transport) -> None:
        self.transport = transport

    def datagram_received(self, data, addr) -> None:
        request_key = INITIAL_KEY if data[0x26] == 0x65 else SESSION_KEY
        request = parse_packet(data, request_key)
        self.requests.append(request.command)
        if request.command == 0x65:
            payload = DEVICE_ID + SESSION_KEY + (b"\0" * 16)
            response = build_packet(0x65, request.sequence, MAC_BYTES, b"\0" * 4, payload, INITIAL_KEY)
        else:
            body = bytearray(23)
            body[2] = 7
            body[10] = (22 << 3) | 6
            body[12] = 0x80
            body[13] = 5 << 5
            body[15] = 1 << 5
            body[18] = 1 << 5
            body[20] = 1 << 3
            response = build_packet(
                0x6A,
                request.sequence,
                MAC_BYTES,
                DEVICE_ID,
                build_application_frame(bytes(body)),
                SESSION_KEY,
            )
        self.transport.sendto(response, addr)


class DeviceTests(unittest.IsolatedAsyncioTestCase):
    def test_new_device_uses_random_initial_sequence(self) -> None:
        with patch(
            "custom_components.broadlink_ac.protocol.device.secrets.randbelow",
            return_value=0x1234,
        ):
            device = AcDevice("127.0.0.1", MAC)

        self.assertEqual(device.sequence, 0x1234)

    async def test_authentication_and_state_read_use_one_local_udp_client(self) -> None:
        loop = asyncio.get_running_loop()
        server = FakeDeviceProtocol()
        try:
            transport, _ = await loop.create_datagram_endpoint(
                lambda: server,
                local_addr=("127.0.0.1", 0),
            )
        except PermissionError as err:
            self.skipTest(f"sandbox does not permit UDP sockets: {err}")
        port = transport.get_extra_info("sockname")[1]
        device = AcDevice("127.0.0.1", MAC, port)

        try:
            session = await device.authenticate()
            with self.assertLogs("custom_components.broadlink_ac.protocol.device", level="DEBUG") as logs:
                state = await device.read_state()
        finally:
            await device.close()
            transport.close()

        self.assertEqual(session["device_id"], DEVICE_ID.hex())
        self.assertEqual(session["device_key"], SESSION_KEY.hex())
        self.assertEqual(state.target_temperature, 30.5)
        self.assertTrue(state.power)
        self.assertEqual(state.vertical_swing_code, 6)
        self.assertEqual(server.requests, [0x65, 0x6A])
        self.assertTrue(any("STATE response" in message for message in logs.output))
