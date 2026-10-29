import unittest

from custom_components.broadlink_ac.protocol.packet import (
    AES_IV,
    INITIAL_KEY,
    broadlink_checksum,
    build_application_frame,
    build_discovery_packet,
    build_get_frame,
    build_packet,
    decrypt_payload,
    encrypt_payload,
    parse_application_frame,
    parse_packet,
)
from custom_components.broadlink_ac.protocol.discovery import parse_discovery_response
from custom_components.broadlink_ac.protocol.state import (
    AcState,
    build_set_data,
    parse_ambient_response,
    parse_state_response,
)


GET_DATA = bytes.fromhex("BB 00 06 80 00 00 02 00 11 01 2B 7E")
SET_DATA = bytes.fromhex(
    "BB 00 06 80 00 00 0F 00 01 01 40 00 0F 20 00 20 00 00 20 00 18 00 00"
)


class ProtocolTests(unittest.TestCase):
    def test_known_get_application_frame_has_zero_checksum(self) -> None:
        frame = build_get_frame(GET_DATA)

        self.assertEqual(frame, bytes.fromhex("0C 00 BB 00 06 80 00 00 02 00 11 01 2B 7E 00 00"))

    def test_set_application_frame_is_padded_to_32_bytes(self) -> None:
        frame = build_application_frame(SET_DATA)

        self.assertEqual(len(frame), 32)
        self.assertEqual(frame[0], 25)
        self.assertEqual(frame[1], 0)
        self.assertEqual(frame[2:25], SET_DATA)
        self.assertEqual(int.from_bytes(frame[25:27], "big"), 0xA73D)
        self.assertEqual(frame[27:], b"\0" * 5)
        self.assertEqual(parse_application_frame(frame), SET_DATA)

    def test_packet_contains_protocol_header_and_checksums(self) -> None:
        mac = bytes.fromhex("34 EA 34 5B 0F D4")
        device_id = bytes.fromhex("01 02 03 04")
        frame = build_get_frame(GET_DATA)
        packet = build_packet(0x6A, 0x1234, mac, device_id, frame, INITIAL_KEY)

        self.assertEqual(packet[:8], bytes.fromhex("5A A5 AA 55 5A A5 AA 55"))
        self.assertEqual(packet[0x24:0x26], bytes.fromhex("2A 4E"))
        self.assertEqual(packet[0x26], 0x6A)
        self.assertEqual(int.from_bytes(packet[0x28:0x2A], "little"), 0x1234)
        self.assertEqual(packet[0x2A:0x30], mac)
        self.assertEqual(packet[0x30:0x34], device_id)
        self.assertEqual(int.from_bytes(packet[0x34:0x36], "little"), broadlink_checksum(frame))

        packet_for_checksum = bytearray(packet)
        packet_for_checksum[0x20:0x22] = b"\0\0"
        self.assertEqual(
            int.from_bytes(packet[0x20:0x22], "little"),
            broadlink_checksum(packet_for_checksum),
        )
        parsed = parse_packet(packet, INITIAL_KEY)
        self.assertEqual(parsed.command, 0x6A)
        self.assertEqual(parsed.sequence, 0x1234)
        self.assertEqual(parsed.payload, frame)

    def test_payload_round_trip_uses_aes_cbc_without_pkcs7(self) -> None:
        payload = bytes(range(32))

        encrypted = encrypt_payload(payload, INITIAL_KEY)

        self.assertNotEqual(encrypted, payload)
        self.assertEqual(decrypt_payload(encrypted, INITIAL_KEY), payload)
        self.assertEqual(AES_IV, bytes.fromhex("56 2E 17 99 6D 09 3D 28 DD B3 BA 69 5A 2E 6F 58"))

    def test_state_response_decodes_documented_fields(self) -> None:
        data = bytearray(23)
        data[10] = (22 << 3) | 6
        data[12] = 0x80
        data[13] = 5 << 5
        data[14] = (1 << 6) | (1 << 7)
        data[15] = (4 << 5) | (1 << 3) | (1 << 2) | (1 << 1)
        data[18] = (1 << 5) | (1 << 1) | (1 << 2)
        data[20] = (1 << 4) | (1 << 3)
        response_body = bytearray(23)
        response_body[2] = 7
        response_body[10:] = data[10:]
        response = bytes([25, 0]) + bytes(response_body)

        state = parse_state_response(response)

        self.assertEqual(state.target_temperature, 30.5)
        self.assertTrue(state.power)
        self.assertEqual(state.mode_code, 4)
        self.assertEqual(state.fan_speed_code, 5)
        self.assertTrue(state.turbo)
        self.assertTrue(state.mute)
        self.assertEqual(state.vertical_swing_code, 6)
        self.assertEqual(state.horizontal_swing_code, 0)
        self.assertTrue(state.health)
        self.assertTrue(state.clean)
        self.assertTrue(state.ifeel)
        self.assertTrue(state.fahrenheit)
        self.assertTrue(state.display_raw)
        self.assertTrue(state.mildew)

    def test_ambient_response_uses_sensor_presence_bit(self) -> None:
        response = bytearray(40)
        response[2 + 15] = 0x25
        response[2 + 31] = 7

        self.assertEqual(parse_ambient_response(bytes(response)), 5.7)

        response[2 + 15] = 0x05
        self.assertIsNone(parse_ambient_response(bytes(response)))

    def test_discovery_response_reverses_mac_and_falls_back_to_mac_name(self) -> None:
        response = bytearray(0x41)
        response[0x34:0x36] = (0x4E2A).to_bytes(2, "little")
        response[0x3A:0x40] = bytes.fromhex("D4 0F 5B 34 EA 34")
        response[-1] = 1

        device = parse_discovery_response(bytes(response), "192.168.1.25")

        self.assertIsNotNone(device)
        assert device is not None
        self.assertEqual(device.mac, "34:ea:34:5b:0f:d4")
        self.assertEqual(device.name, device.mac)
        self.assertTrue(device.cloud_bound)

    def test_set_data_is_built_from_a_full_state(self) -> None:
        state = AcState(
            target_temperature=16.5,
            power=True,
            mode_code=1,
            fan_speed_code=2,
            vertical_swing_code=3,
            horizontal_swing_code=7,
            sleep=True,
            display_raw=True,
            mildew=True,
            health=True,
            clean=True,
            ifeel=True,
            fahrenheit=True,
            turbo=False,
            mute=False,
        )

        data = build_set_data(state)

        self.assertEqual(len(data), 23)
        self.assertEqual(data[0:10], bytes.fromhex("BB 00 06 80 00 00 0F 00 01 01"))
        self.assertEqual(data[10], (8 << 3) | 3)
        self.assertEqual(data[11], 7 << 5)
        self.assertEqual(data[12], 0x8F)
        self.assertEqual(data[13], 2 << 5)
        self.assertEqual(data[14], 0)
        self.assertEqual(data[15], (1 << 5) | (1 << 3) | (1 << 2) | (1 << 1))
        self.assertEqual(data[18], (1 << 5) | (1 << 1) | (1 << 2))
        self.assertEqual(data[20], (1 << 4) | (1 << 3))

    def test_discovery_packet_contains_local_time_and_endpoint(self) -> None:
        packet = build_discovery_packet(
            "192.168.1.20",
            54321,
            year=2026,
            month=10,
            day=29,
            hour=12,
            minute=34,
            weekday=4,
            utc_offset_seconds=10800,
        )

        self.assertEqual(len(packet), 0x30)
        self.assertEqual(packet[0x08], 3)
        self.assertEqual(packet[0x0C:0x0E], bytes.fromhex("EA 07"))
        self.assertEqual(packet[0x0E:0x14], bytes([34, 12, 26, 4, 29, 10]))
        self.assertEqual(packet[0x18:0x1C], bytes([192, 168, 1, 20]))
        self.assertEqual(int.from_bytes(packet[0x1C:0x1E], "little"), 54321)
        self.assertEqual(packet[0x26], 6)


if __name__ == "__main__":
    unittest.main()
