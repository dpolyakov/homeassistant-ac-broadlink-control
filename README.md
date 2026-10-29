# Broadlink AUX Air Conditioner for Home Assistant

This custom integration controls compatible AUX / AC Freedom air conditioners locally over UDP. It does not require MQTT, a bridge daemon, or an AUX cloud account.

## Supported devices

The integration accepts devices reporting Broadlink `devtype == 0x4E2a` (20010). Compatibility is device-firmware dependent even when the same device type is reported.

The implementation was designed for devices such as AUX, Dunham-Bush, Rcool, Akai, Rinnai, Tornado X, and Ballu units using an AC Freedom Wi-Fi module. This list is not a live compatibility guarantee.

## Installation

Install the `custom_components/broadlink_ac` directory through HACS as a custom repository or copy it into the Home Assistant configuration directory. Restart Home Assistant, then add **Broadlink AC** from Settings → Devices & services.

The manifest documentation URL must point to the repository hosting this integration before publishing it as a public HACS repository.

## Configuration

The config flow offers:

- manual IPv4, MAC address, optional UDP port, and optional name;
- an explicit three-second UDP discovery scan.

Manual configuration remains available when broadcast is blocked. The default device port is 80. A MAC address identifies the device; changing its DHCP address does not create a duplicate entry.

Options are:

- display inversion;
- poll interval from 10 to 300 seconds;
- device name.

Temperature values use Home Assistant's global unit system. The wire protocol always uses Celsius and half-degree increments.

## Entities

Each configured device creates one climate entity with:

- HVAC modes: off, auto, cool, dry, heat, fan-only;
- fan modes: auto, low, medium, high, turbo, mute;
- independent vertical and horizontal swing modes;
- target temperature from 16 to 32 °C in 0.5 °C steps;
- current temperature from the device ambient sensor when present.

It also creates switches for display, health, clean, and mildew protection, plus diagnostic sensors for the last successful packet and error count.

The device requires complete state writes. A control action is debounced for 300 ms, serialised behind the per-device UDP queue, followed by a 500 ms settling pause and a confirmation GET.

## Troubleshooting

### Authentication or checksum errors

The most common cause is a lost pairing between the Wi-Fi module and AC Freedom. Stop every other controller for this device, unbind or remove the device in AC Freedom, reset the Wi-Fi module, pair it again, and retry the integration.

The integration retries one re-authentication for an authentication or protocol error. It does not delete persisted credentials automatically.

### The device is not discovered

Broadcast may be blocked by the access point or VLAN. Use manual setup with the device IPv4 address and MAC address. The device must respond locally; NAT, VPN, and cloud-only connectivity are not supported.

### Two controllers are running

Do not run the old MQTT bridge and this integration against the same air conditioner. Both controllers can authenticate and change the session state, causing intermittent failures.

### A switch or swing position does not work

The protocol exposes fields that are not implemented identically by every firmware version. Check DEBUG logs and the live acceptance checklist. An unsupported physical feature is not evidence that the local transport is broken.

## Diagnostics and logging

At DEBUG level the protocol logs raw packet hex to help investigate incompatible firmware. Session keys are never logged. Diagnostics redact host and MAC identity and contain only safe state and counters; raw captures are not persisted automatically.

## Development checks

The independent protocol tests run with Python's standard `unittest` runner:

```sh
/path/to/python3 -m unittest discover -s tests -v
/path/to/python3 -m compileall -q custom_components tests
```

Captured response fixtures are deliberately kept separate from synthetic fixtures. Until real auth, state, and ambient response captures are added, protocol tests verify the written specification and deterministic mocks, not complete hardware compatibility.

## Scope

Version 1 is local-only. MQTT, external daemons, AUX Cloud, IPv6, NAT traversal, VPN transport, and automatic pairing reset are out of scope.
