# Broadlink AUX Air Conditioner

[English](README.md) | [Русский](README.ru.md)

A custom Home Assistant integration for controlling compatible [AUX](https://www.auxair.com/) air conditioners over the local network. It communicates directly with the air conditioner’s Broadlink-compatible Wi-Fi module over IPv4 UDP. The integration does not use MQTT, an external bridge, or AUX Cloud.

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
- **Enter device manually** asks for the device’s IPv4 address and MAC address. The UDP port defaults to `80`.

If discovery finds no device, use manual setup. The selected device must still be reachable over the local network.

## Options

After setup, the integration’s options let you invert display-switch behavior and select optional switches. To rename a device, open its device page in Home Assistant and edit its name.

Optional switches are disabled for a newly added device. Enable only the functions listed in the device’s manual. Selecting a switch does not verify that the physical device supports it.

## Data updates

The integration polls device state every 10 seconds, so changes made with the remote become visible without excessive UDP traffic. Ambient temperature is requested every 180 seconds and when the I-feel state changes. Commands trigger a state readback. Home Assistant can [define a custom polling interval](https://www.home-assistant.io/common-tasks/general/#defining-a-custom-polling-interval) through an automation after disabling automatic polling in the integration's system options.

## Actions, triggers, and conditions

The integration adds no custom actions, triggers, or conditions. Use Home Assistant's standard climate and switch actions and entity state triggers/conditions in automations.

## Removal

1. Open **Settings → Devices & services → Broadlink AUX Air Conditioner**.
2. Open the menu for the device's integration entry and select **Delete**. Repeat for other configured air conditioners if needed.
3. To remove the integration files, uninstall it in HACS, or delete `custom_components/broadlink_ac` for a manual installation, then restart Home Assistant.

Removal stops local polling. It does not switch the air conditioner off, reset its settings, or unpair it from AC Freedom. No cloud authorization was created by this integration. Cached local session data may remain in `<config>/.storage/broadlink_ac.<entry_id>.json`; after deleting the entry, you may remove that file with Home Assistant stopped if you want to clear the cached session.

## Troubleshooting

### No devices found

The access point or network segmentation may block UDP broadcast. Enter the device’s IPv4 address and MAC address manually.

### Authentication failed

Check that the Wi-Fi module is paired in AC Freedom; if authentication still fails, re-pair the module in that app. If another bridge or controller is managing the same air conditioner, stop it before using this integration; multiple controllers can interfere with the device’s session state.

### A switch or swing position does not work

Feature support depends on the device model and firmware. Check the device manual before enabling optional switches.

## Diagnostics and logs

Home Assistant diagnostics redact the device’s host and MAC address and do not include raw packets or session keys. DEBUG logs include packet direction, command, sequence, length, and decoded state fields, but no raw packets, payloads, or session keys. Logs still contain the device’s IP address; review them before sharing.

## Protocol implementation reference

Reference for the protocol implementation: [broadlink_ac_mqtt](https://github.com/liaan/broadlink_ac_mqtt) (archived repository).

## Scope

The integration controls devices locally over IPv4 UDP. MQTT, external bridge software, AUX Cloud, IPv6, NAT traversal, and VPN transport are not supported.


## Development and quality checks

Use Python 3.14 with Home Assistant 2026.9 for the test environment:

```sh
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
./scripts/check
```

The check runs the protocol tests and Home Assistant flow/lifecycle tests, and requires 100% line and branch coverage of `config_flow.py`. CI also runs HACS and hassfest without ignored checks. The HA tests mock device I/O; they do not demonstrate behavior on physical hardware.

[`quality_scale.yaml`](custom_components/broadlink_ac/quality_scale.yaml) records the applicable Bronze requirements and exemptions. This is a self-assessment for a custom integration, not an official Bronze tier awarded by Home Assistant. See the [quality scale](https://contributors.home-assistant.io/core/quality-scale/tiers/) and [custom brand asset rules](https://contributors.home-assistant.io/core/integrations/brands/#brand-images-for-custom-integrations).
