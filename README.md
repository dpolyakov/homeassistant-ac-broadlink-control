# Broadlink AUX Air Conditioner

[English](README.md) | [Русский](README.ru.md)

A custom Home Assistant integration for controlling compatible AUX air conditioners over the local network. It communicates directly with the air conditioner’s Broadlink-compatible Wi-Fi module over IPv4 UDP. The integration does not use MQTT, an external bridge, or AUX Cloud.

## Compatibility

The integration supports devices that report Broadlink device type `0x4E2a` (`20010`). Compatibility depends on the device model and firmware, even when the device type matches. The device must be reachable from Home Assistant over local IPv4 UDP.

## Features

- A native climate entity with `off`, `auto`, `cool`, `dry`, `heat`, and `fan_only` modes.
- Fan modes `auto`, `low`, `medium`, `high`, `turbo`, and `mute`.
- Independent vertical and horizontal swing controls.
- Target temperature from 16 to 32 °C in 0.5 °C increments. The climate entity follows Home Assistant’s configured temperature unit.
- The device’s ambient-temperature reading on the climate entity and as a `Built-in temperature` sensor. The value is unavailable when the device does not report it.
- A read-only `I-feel` binary sensor.
- Optional switches for `Display`, `Health`, `Clean`, and `Mildew protection`.
- Diagnostic sensors for the last successful packet time and the error count.

The local protocol provides one ambient-temperature value. The climate entity and `Built-in temperature` sensor use that same reading; there is no separate remote-control temperature sensor. The `I-feel` sensor is read-only and reflects the device’s state.

## Installation

### HACS

The root `hacs.json` sets the name shown in HACS. The integration’s `manifest.json` defines the required `issue_tracker` field, and the repository includes its brand icon at `custom_components/broadlink_ac/brand/icon.png` ([HACS general requirements](https://hacs.xyz/docs/publish/start/), [integration requirements](https://hacs.xyz/docs/publish/integration/)).

To install this integration from the repository through HACS:

1. In HACS, open the menu in the top-right corner and select **Custom repositories**.
2. Add [`https://github.com/dpolyakov/homeassistant-ac-broadlink-control`](https://github.com/dpolyakov/homeassistant-ac-broadlink-control) and choose **Integration** as the category.
3. Add and install **Broadlink AUX Air Conditioner**, then restart Home Assistant.

See the [HACS custom repository guide](https://hacs.xyz/docs/faq/custom_repositories/) for details.

### Manual installation

1. Copy `custom_components/broadlink_ac` from this repository into `<Home Assistant config>/custom_components/broadlink_ac`.
2. Restart Home Assistant.

## Add the integration

In Home Assistant, open **Settings → Devices & services → Add integration** and search for **Broadlink AUX Air Conditioner**. The setup flow offers two methods:

- **Find devices** sends a local UDP broadcast scan for three seconds. Discovery requires the network to pass the broadcast packets.
- **Enter device manually** asks for the device’s IPv4 address and MAC address. The UDP port defaults to `80`; a device name is optional.

If discovery finds no device, use manual setup. The selected device must still be reachable over the local network.

## Options

After setup, the integration’s options let you change the device name, set the polling interval from 10 to 300 seconds (10 seconds by default), invert display-switch behavior, and select optional switches.

Optional switches are disabled for a newly added device. Enable only the functions listed in the device’s manual. Selecting a switch does not verify that the physical device supports it.

## Troubleshooting

### No devices found

The access point or network segmentation may block UDP broadcast. Enter the device’s IPv4 address and MAC address manually.

### Authentication failed

Check that the Wi-Fi module is paired in AC Freedom; if authentication still fails, re-pair the module in that app. If another bridge or controller is managing the same air conditioner, stop it before using this integration; multiple controllers can interfere with the device’s session state.

### A switch or swing position does not work

Feature support depends on the device model and firmware. Check the device manual before enabling optional switches.

## Diagnostics and logs

Home Assistant diagnostics redact the device’s host and MAC address and do not include raw packets or session keys. DEBUG logging includes raw UDP packet data; review logs before sharing them.

## Protocol implementation reference

Reference for the protocol implementation: [broadlink_ac_mqtt](https://github.com/liaan/broadlink_ac_mqtt) (archived repository).

## Scope

The integration controls devices locally over IPv4 UDP. MQTT, external bridge software, AUX Cloud, IPv6, NAT traversal, and VPN transport are not supported.

