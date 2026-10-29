# Broadlink AUX / AC Freedom local protocol

Status labels used here:

- **confirmed** — directly specified by the current reverse-engineered contract;
- **captured** — backed by a sanitized real packet capture;
- **inferred** — implemented from a reference implementation but not independently captured;
- **experimental** — kept because a reference exposes it, but not guaranteed by every model.

This repository currently contains no captured real response fixtures. Request bytes and formulas below are **confirmed by the written specification**; response behavior remains to be verified on hardware.

## Transport

- IPv4 UDP.
- Device port: 80 by default; the config flow allows a different port.
- Discovery destination: `255.255.255.255:80`.
- One socket and one outstanding request per device.
- Minimum interval between sent packets: 500 ms.
- Response timeout: 1 second.
- Overall operation timeout: 10 seconds.

## Device identity

- Supported device type: little-endian `0x4E2a` (20010).
- Packet device type bytes: `2A 4E`.
- Discovery MAC bytes are reversed and must be reversed back before storage.
- Config-entry identity is the normalized MAC address.

## Broadlink checksum

The checksum starts at `0xBEAF` and adds every byte modulo 16 bits:

```text
checksum = 0xBEAF
for byte in data:
    checksum = (checksum + byte) & 0xFFFF
```

The stored value is little-endian.

## Discovery request

The request is 48 zero-initialized bytes:

| Offset | Meaning |
| --- | --- |
| `0x08` | signed local timezone hour; positive values use one byte, negative values use two's-complement lower byte and `FF FF FF` in the remaining bytes |
| `0x0C..0x0D` | year, little-endian |
| `0x0E` | minute |
| `0x0F` | hour |
| `0x10` | year modulo 100 |
| `0x11` | ISO weekday, 1..7 |
| `0x12` | day |
| `0x13` | month |
| `0x18..0x1B` | local IPv4 address |
| `0x1C..0x1D` | local bound port, little-endian |
| `0x20..0x21` | Broadlink checksum |
| `0x26` | `6` |

Discovery responses are accepted only when the device type at `0x34..0x35` equals `0x4E2a`.

| Offset | Meaning |
| --- | --- |
| `0x34..0x35` | device type, little-endian |
| `0x3A..0x3F` | MAC in reverse order |
| `0x40..` | UTF-8 name up to NUL; the last byte is the cloud-bound flag |

Discovery runs only after an explicit user action and lasts three seconds. Results are deduplicated by MAC.

## Authentication command `0x65`

The plaintext payload is 80 bytes initialized to zero:

- `0x04..0x12`: fifteen ASCII `1` bytes;
- `0x1E`: `01`;
- `0x2D`: `01`;
- `0x30..0x36`: ASCII `Test  1`.

The initial key and fixed IV are:

```text
key = 09 76 28 34 3F E9 9E 23 76 5C 15 13 AC CF 8B 02
iv  = 56 2E 17 99 6D 09 3D 28 DD B3 BA 69 5A 2E 6F 58
```

The response error is `response[0x22] | response[0x23] << 8`. A zero error is required. Decrypting the response payload yields:

- bytes `0x00..0x03`: device id;
- bytes `0x04..0x13`: 16-byte session key.

The session id and key are persisted in Home Assistant Store. A protocol/authentication failure permits one re-authentication attempt; pairing data is not deleted automatically.

## Packet format

The unencrypted header is 56 bytes:

| Offset | Meaning |
| --- | --- |
| `0x00..0x07` | `5A A5 AA 55 5A A5 AA 55` |
| `0x20..0x21` | checksum of the complete packet with this field zeroed |
| `0x22..0x23` | response error code |
| `0x24..0x25` | device type `2A 4E` |
| `0x26` | command: `65` auth or `6A` application data |
| `0x28..0x29` | sequence, little-endian |
| `0x2A..0x2F` | MAC in normal order |
| `0x30..0x33` | device id |
| `0x34..0x35` | Broadlink checksum of plaintext payload |
| `0x38..` | AES-128-CBC ciphertext |

AES uses the fixed IV above and either the initial key or persisted session key. Plaintext payloads are zero-padded to a 16-byte AES block boundary; no PKCS#7 padding is used.

## Application frame

The plaintext application frame is:

```text
[len(data) + 2] [00] [data...] [checksum_hi] [checksum_lo] [zero padding]
```

The application checksum is a big-endian ones-complement checksum over 16-bit big-endian words. An odd final byte is paired with zero before summing. The folded sum is inverted.

The documented GET data is 12 bytes and produces a 16-byte frame:

```text
BB 00 06 80 00 00 02 00 11 01 2B 7E
```

The documented ambient GET changes byte 8 to `21` and uses:

```text
BB 00 06 80 00 00 02 00 21 01 1B 7E
```

The documented SET data is 23 bytes and produces a 32-byte frame after zero padding.

## State GET

The state request uses application command `0x6A` and the GET data above. The result must have:

- decrypted frame length byte `0x19`;
- result marker at decrypted offset `0x04` equal to `0x07`;
- target temperature at least 16 °C.

After the first two frame bytes are discarded, the fields are:

| Field | Expression |
| --- | --- |
| target temperature | `8 + (b[10] >> 3) + 0.5 * (b[12] >> 7)` |
| power | `(b[18] >> 5) & 1` |
| vertical swing | `b[10] & 0b111` |
| mode | `(b[15] >> 5) & 0b1111` |
| sleep | `(b[15] >> 2) & 1` |
| display raw bit | `(b[20] >> 4) & 1` |
| mildew | `(b[20] >> 3) & 1` |
| health | `(b[18] >> 1) & 1` |
| fan speed | `(b[13] >> 5) & 0b111` |
| ifeel | `(b[15] >> 3) & 1` |
| mute | `(b[14] >> 7) & 1` |
| turbo | `(b[14] >> 6) & 1` |
| clean | `(b[18] >> 2) & 1` |
| horizontal swing | `(b[11] >> 5) & 0b111` |

Known mode codes are 0 auto, 1 cool, 2 dry, 4 heat, and 6 fan-only. Power off is exposed as Home Assistant `off` regardless of the retained mode code.

Known fan codes are 0 none, 1 high, 2 medium, 3 low, and 5 auto. Turbo takes precedence over ordinary fan speed; mute takes precedence over turbo. Selecting a normal fan mode clears both special bits.

Vertical swing codes are 0 off, 1 top, 2 middle1, 3 middle2, 4 middle3, 5 bottom, 6 swing, and 7 auto.

Horizontal swing codes are 0 left-right flap, 1 left flap, 2 left fix, 5 right flap, 6 right fix, and 7 left-right fix. Other values remain experimental and do not get silently mapped to a known value.

## Ambient GET

The ambient request uses the same application command with byte 8 equal to `0x21`. The response must be at least 40 bytes after decryption and frame extraction.

The selected v1 interpretation is:

```text
raw = b[15]
if raw & 0x20:
    ambient = (raw & 0x1F) + b[31] / 10
else:
    ambient = None
```

The Python and Go references disagree about the presence bit and fraction masking. This remains an explicit experimental point for live hardware validation.

## Full SET

SET always sends all 23 data bytes:

```text
0:  BB
1:  00
2:  06
3:  80
4:  00
5:  00
6:  0F
7:  00
8:  01
9:  01
10: ((int(T) - 8) << 3) | vertical_swing
11: horizontal_swing << 5
12: 0x0F | (0x80 if T has a half degree)
13: fan_speed << 5
14: (turbo << 6) | (mute << 7)
15: (mode << 5) | (sleep << 2)
16: 00
17: 00
18: (power << 5) | (health << 1) | (clean << 2)
19: 00
20: (display_raw << 4) | (mildew << 3)
21: 00
22: 00
```

The accepted target range is 16–32 °C in 0.5 °C increments. The physical display bit is inverted by default: raw zero means display on. The integration option `invert_display` handles models with reverse behavior.

## Lifecycle and acceptance

- Poll state every 10 seconds by default; allow 10–300 seconds in options.
- Poll ambient every 180 seconds.
- Mark unavailable after three consecutive failed operations and available after one success.
- Use a 300 ms command debounce, 500 ms minimum packet spacing, 500 ms post-SET delay, and bounded retry/backoff.
- Test packet construction and parsing with deterministic golden data.
- Keep real captured responses separate from synthetic fixtures.
- Validate on hardware where available: power, supported HVAC/fan modes, temperature increments, both swing axes, switches, ambient, offline, recovery, and rapid command coalescing.
