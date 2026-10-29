Type: feature
Status: ready-for-agent
Labels: ready-for-agent

# Broadlink AC Home Assistant integration

## Problem Statement

The user has an AUX / AC Freedom air conditioner with a Broadlink-compatible Wi-Fi module. The device can be controlled locally over UDP, but the current integration model requires an external MQTT bridge and broker.

That setup adds an unnecessary runtime dependency, duplicates Home Assistant state through MQTT discovery, complicates troubleshooting, and prevents the device from being represented as a native Home Assistant climate device.

The repository is a clean starting point with no existing implementation, glossary, ADRs, or test suite. The feature therefore needs a complete, self-contained custom integration and its supporting documentation and tests.

## Solution

Build a HACS-ready custom Home Assistant integration for local control of Broadlink-compatible AUX / AC Freedom devices. The integration communicates directly with each device over IPv4 UDP, performs the documented AES-128-CBC protocol exchange, exposes native Home Assistant entities, and persists the device session data needed to avoid unnecessary re-authentication.

The integration will support devices reporting `devtype == 0x4E2a` (20010). It will provide manual configuration and explicit UDP discovery, independent per-device polling and command queues, robust retry and offline handling, and a testable protocol implementation.

The primary behavioral test seam is:

`config flow -> config entry -> coordinator/entities -> protocol client <-> deterministic mock UDP device`

Packet golden tests, captured protocol fixtures, static checks, and live hardware checks support this seam but do not replace it.

## User Stories

1. As a Home Assistant user, I want to add my Broadlink-compatible air conditioner through a native config flow, so that I do not need MQTT or an external daemon.
2. As a Home Assistant user, I want to enter the device IP, MAC address, port, and optional name manually, so that the integration works when UDP broadcast is blocked.
3. As a Home Assistant user, I want to start an explicit UDP discovery scan, so that compatible devices on my local network can populate their configuration fields automatically.
4. As a Home Assistant user, I want discovery results filtered to `devtype == 0x4E2a`, so that unsupported devices are not presented as compatible air conditioners.
5. As a Home Assistant user, I want discovery results deduplicated by normalized MAC address, so that one physical device does not appear multiple times.
6. As a Home Assistant user, I want the discovery name used when it is meaningful, but a MAC-based fallback when the device name is empty or unusable, so that every device has a stable human-readable label.
7. As a Home Assistant user, I want to override the discovered name, so that the device is recognizable in my Home Assistant installation.
8. As a Home Assistant user, I want the integration to reject duplicate config entries for the same MAC address, so that one device cannot create conflicting coordinators.
9. As a Home Assistant user, I want a config entry to survive DHCP changes, so that changing the IP updates the existing device rather than creating a new device identity.
10. As a Home Assistant user, I want the initial setup to authenticate and read the device state before creating the entry, so that invalid credentials, unsupported devices, and unreachable devices are reported immediately.
11. As a Home Assistant user, I want actionable setup errors for connection failure, authentication failure, invalid responses, and unsupported device types, so that I know what to fix.
12. As a Home Assistant user, I want the integration to explain that persistent authentication/checksum failures may require re-pairing the Wi-Fi module in AC Freedom, so that I can recover a lost pairing without guessing.
13. As a Home Assistant user, I want one native climate entity per air conditioner, so that the device appears and behaves like other Home Assistant climate devices.
14. As a Home Assistant user, I want to turn the air conditioner off and on, so that power control is available through standard climate actions.
15. As a Home Assistant user, I want to use auto, cool, dry, heat, and fan-only modes, so that the supported operating modes are available in Home Assistant.
16. As a Home Assistant user, I want power-off to preserve target temperature, mode, fan, and swing settings, so that turning the device back on does not erase my preferences.
17. As a Home Assistant user, I want to set a target temperature from 16 to 32 °C in 0.5 °C increments, so that the integration matches the device protocol.
18. As a Home Assistant user whose Home Assistant unit system is Fahrenheit, I want temperatures converted at the entity boundary, so that the UI uses my global unit system while the protocol remains in Celsius.
19. As a Home Assistant user, I want auto, low, medium, high, turbo, and mute fan modes, so that special fan behavior is controllable through the climate entity.
20. As a Home Assistant user, I want selecting turbo or mute to clear the conflicting fan mode, so that the device receives a valid mutually exclusive state.
21. As a Home Assistant user, I want vertical swing positions including off, fixed positions, swing, and auto, so that I can direct airflow vertically.
22. As a Home Assistant user, I want horizontal swing exposed independently from vertical swing, so that a device supporting horizontal movement can be controlled on both axes.
23. As a Home Assistant user, I want horizontal swing to preserve its value during a full state SET, so that changing temperature or fan speed does not unexpectedly reset the horizontal position.
24. As a Home Assistant user, I want the current temperature populated from the device ambient-temperature command, so that the climate card can show the measured room temperature.
25. As a Home Assistant user, I want the current temperature to be unknown when the device reports that no ambient sensor is available, so that the integration does not fabricate a measurement from the target temperature.
26. As a Home Assistant user, I want display control, health/ionization, clean, and mildew-protection controls, so that all protocol-backed device functions are available as native switches.
27. As a Home Assistant user, I want switch changes to use the same confirmed state model as climate changes, so that climate and switch entities cannot contradict each other.
28. As a Home Assistant user, I want the integration to update optimistically while a command is in flight, so that the UI responds immediately to my action.
29. As a Home Assistant user, I want a failed command to revert to the last confirmed state, so that the UI does not claim that the device changed when it did not.
30. As a Home Assistant user, I want multiple rapid changes to be combined into one SET, so that moving a temperature control does not flood the device with packets.
31. As a Home Assistant user, I want a full state SET to read the current state first when necessary, so that changing one field does not overwrite unrelated device settings.
32. As a Home Assistant user, I want the integration to wait before the control GET after a SET, so that the device has time to apply the command before confirmation.
33. As a Home Assistant user, I want each device polled independently, so that an unplugged air conditioner does not delay or disable another one.
34. As a Home Assistant user, I want a device to become unavailable only after three consecutive failed operations, so that transient Wi-Fi problems do not cause UI flapping.
35. As a Home Assistant user, I want a device to become available again after the first successful exchange, so that recovery is reflected promptly.
36. As a Home Assistant user, I want polling to back off after repeated failures, so that an offline device is not continuously hammered.
37. As a Home Assistant user, I want manual commands to receive a fresh attempt even while background polling is backing off, so that an offline device can be tested or recovered interactively.
38. As a Home Assistant user, I want the integration to reuse persisted authentication data after restart, so that the device does not need unnecessary pairing on every Home Assistant boot.
39. As a Home Assistant user, I want one controlled re-authentication attempt after an authentication or protocol failure, so that stale session data can recover without an infinite retry loop.
40. As a Home Assistant user, I want persisted device keys protected from logs and diagnostics, so that troubleshooting does not disclose credentials.
41. As a Home Assistant user, I want DEBUG logging to include raw packet hex when diagnosing an incompatible model, so that protocol failures can be investigated from evidence.
42. As a Home Assistant user, I want exported diagnostics to redact MAC addresses and other identifying data, so that I can share diagnostics safely.
43. As a Home Assistant user, I want diagnostic sensors for the last successful packet and error count, so that I can build automations and dashboards for device health.
44. As a Home Assistant maintainer, I want the protocol implementation to be independent of Home Assistant imports, so that packet construction, parsing, encryption, and validation can be tested deterministically.
45. As a Home Assistant maintainer, I want packet checksum and AES behavior covered by golden tests, so that future refactors cannot silently change the wire format.
46. As a Home Assistant maintainer, I want captured response fixtures separated from synthetic fixtures, so that assumptions are not presented as reverse-engineered facts.
47. As a Home Assistant maintainer, I want invalid temperatures and malformed packets rejected as protocol failures, so that corrupt responses do not update entity state.
48. As a Home Assistant maintainer, I want unknown enum values to preserve the last confirmed value and emit a warning, so that the integration does not silently map unsupported device behavior to a false state.
49. As a Home Assistant maintainer, I want a deterministic mock UDP device that can represent at least two independent devices, so that queue isolation and multi-device behavior are tested without hardware.
50. As a Home Assistant maintainer, I want a live hardware checklist separate from automated test results, so that reports distinguish simulated protocol confidence from real device compatibility.
51. As a Home Assistant maintainer, I want unsupported physical functions marked explicitly in live results, so that one test device lacking a feature does not invalidate unrelated protocol coverage.
52. As a Home Assistant user, I want English and Russian installation and troubleshooting documentation, so that I can set up and recover the integration in either language.
53. As a Home Assistant maintainer, I want a canonical protocol document with evidence labels and known discrepancies, so that future protocol work does not repeat the same reverse-engineering effort.
54. As a Home Assistant maintainer, I want the v1 scope to exclude cloud control, so that the local integration remains auditable and does not introduce external service credentials.

## Implementation Decisions

- The implementation is a clean-start custom integration targeting the current stable Home Assistant release at implementation time. Compatibility with older releases is not promised without verification.
- The integration supports local IPv4 UDP only. IPv6, NAT traversal, VPN transport, and cloud backends are outside the v1 contract.
- Only devices reporting `devtype == 0x4E2a` are accepted. Brand and model names from the compatibility list are hypotheses until verified on hardware.
- The integration has a protocol layer with no Home Assistant dependencies. It owns Broadlink checksums, application-frame checksums, AES-128-CBC encryption/decryption, packet construction/parsing, authentication, state parsing, ambient parsing, and device-level UDP operations.
- The Home Assistant layer owns config flow, options, coordinator lifecycle, entities, persistence integration, diagnostics, logging policy, and error translation.
- Each config entry has one coordinator and one serialized per-device operation queue. A device has one active UDP socket and at most one outstanding request. Discovery uses a separate ephemeral socket.
- The device transport enforces at least 500 ms between UDP packets. A command debounce window of 300 ms combines the latest changes by field into one operation.
- A SET always uses read-modify-write semantics. If the coordinator lacks a confirmed state, it reads state first, applies the requested changes, sends the complete state block, waits 500 ms, and performs a control GET.
- Polling uses a default interval of 10 seconds and is configurable from 10 to 300 seconds. Ambient polling is separate and runs every 180 seconds.
- A single operation has a one-second response timeout, no more than three attempts, and a hard ten-second overall timeout. Re-authentication consumes one of the attempts and cannot extend the overall deadline.
- Polling failure backoff uses 2, 4, 8, 16, and 30 seconds, capped at 30 seconds. Successful exchange resets the backoff. Manual commands are not suppressed for the full poll backoff.
- Three consecutive failed operations mark the device and its entities unavailable. Any successful exchange restores availability.
- Timeout and transport failures retry without immediate re-authentication. Authentication, checksum, and protocol failures permit one re-authentication and retry. A `devtype` mismatch is a configuration error. Persistent authentication failure produces an actionable AC Freedom re-pairing message and does not automatically delete persisted credentials.
- Persisted state uses a versioned Home Assistant Store record containing `device_id`, `device_key`, and the 16-bit sequence counter. Store writes are debounced. Missing or unusable sequence data falls back to a random starting counter.
- The normalized MAC is the stable device identity. There is one config entry per MAC, and an IP change updates the existing entry.
- User naming takes precedence over discovery naming, which takes precedence over a normalized MAC fallback.
- Manual configuration requires IP and MAC, accepts an optional name, and defaults the port to 80. The config flow does not expose a per-entry temperature unit.
- Discovery is an explicit three-second scan. Results are deduplicated by normalized MAC and filtered by `devtype`. Manual configuration remains available when discovery finds nothing.
- Initial setup authenticates and reads state before creating the config entry. User-facing errors are translated into stable categories for connection failure, authentication failure, unsupported device, and invalid response.
- Options flow changes only name, poll interval, and `invert_display`.
- The climate entity exposes `off`, `auto`, `cool`, `dry`, `heat`, and `fan_only` HVAC modes. It exposes `auto`, `low`, `medium`, `high`, `turbo`, and `mute` fan modes.
- The climate entity uses 16–32 °C and 0.5 °C precision internally. Home Assistant's global unit system is applied at the entity boundary; protocol values remain Celsius.
- Power-off preserves the last target temperature, mode, fan, and swing values. Turning on restores those settings through a full SET.
- Turbo and mute are mutually exclusive and take precedence over ordinary fan speed when decoding. Selecting either clears the other; selecting an ordinary speed clears both.
- Vertical swing is exposed through the standard climate swing property. Horizontal swing is exposed through Home Assistant's independent horizontal swing property. Both are carried through full state reads and writes.
- The climate entity does not expose `hvac_action` because the protocol does not report compressor action.
- Current temperature comes only from the ambient command. A missing ambient sensor produces an unknown current temperature while leaving the device available.
- Display, health, clean, and mildew switches are created only when selected manually from the device manual. New entries select none by default; existing entries retain all four until configured. Selected switches use the same coordinator state and read-modify-write queue as the climate entity.
- Two diagnostic sensor entities expose the last successful packet time and error count.
- Unknown mode, fan, or swing codes do not silently map to `auto` or `off`. The last confirmed entity value is retained, a warning is logged, and the device remains available unless the packet itself is invalid.
- Raw packet hex is logged at DEBUG for protocol diagnosis. Session keys never appear in logs, diagnostics, or fixtures. Exported diagnostics contain redacted identifying data and safe counters/state only; raw packet dumps are not persisted automatically.
- The integration does not provide a custom refresh service in v1. Coordinator polling and Home Assistant's standard refresh mechanisms are sufficient.
- Device registry metadata uses manufacturer `AUX / Broadlink`, a discovery-derived or fallback model name, and MAC-based stable identifiers.
- Internal enum values are lowercase and not localized. UI translations are maintained separately from protocol values.
- Documentation includes English and Russian README documents and a canonical protocol document. The protocol document labels claims as confirmed, captured, inferred, or experimental and records the ambient interpretation discrepancy and other known limitations.
- The project must remain free of MQTT, cloud requests, external daemons, YAML configuration, and undocumented protocol-byte changes without an explicit evidence label.

## Testing Decisions

- The primary test seam is the complete Home Assistant behavior from config flow through coordinator and entities to a deterministic mock UDP device. Tests assert external behavior and observable protocol effects, not private class structure or implementation details.
- Protocol tests cover Broadlink packet magic, device type, MAC ordering, sequence handling, checksum placement, application-frame checksum, AES-128-CBC encryption/decryption, padding, authentication response parsing, and malformed packet rejection.
- Golden request tests use deterministic known keys, counters, payloads, and expected wire bytes. They do not use user credentials.
- Response tests distinguish synthetic fixtures from captured fixtures. Captured auth, state, and ambient responses are required before those paths can be described as fully verified against hardware. Synthetic fixtures may verify parser behavior but must remain labeled synthetic.
- State parser tests cover temperature and half-degree decoding, power, mode, sleep, display, mildew, health, fan, ifeel, mute, turbo, clean, vertical swing, horizontal swing, missing ambient sensor, unknown enum values, invalid temperatures, and invalid frame lengths.
- Coordinator tests cover one-outstanding-request behavior, 500 ms transport spacing, 300 ms command debounce, full SET construction, post-SET delay, control GET, poll scheduling, ambient scheduling, optimistic update and rollback, three-failure availability threshold, recovery, re-authentication, and poll backoff.
- Config-flow tests cover manual setup, explicit discovery, deduplication, unsupported device filtering, duplicate MAC rejection, connection/auth/protocol failures, successful initial state read, name precedence, and options validation.
- Entity tests cover climate modes, fan exclusivity, power-off preservation, Celsius/Fahrenheit boundary conversion, independent vertical and horizontal swing, all four switches, diagnostic sensors, stable unique IDs, and shared confirmed state.
- Mock multi-device tests run at least two independent devices and verify that a failed or delayed device does not block commands, state, or availability for the other device.
- Static and quality checks include Python import/compile checks, `ruff`, `hassfest`, and the configured Home Assistant test runner. `mypy` is used only if a coherent project configuration and dependencies are provided.
- Live acceptance is reported separately from automated checks. The checklist covers power, every device-supported HVAC mode, 0.5 °C changes, every device-supported fan mode including turbo/mute, vertical and horizontal swing, display, health, clean, mildew, ambient updates, offline after approximately three failed polls, recovery, and command debounce. Unsupported physical functions are marked explicitly rather than treated as protocol failures.

## Out of Scope

- MQTT broker integration, MQTT discovery, LWT, and the external bridge/daemon model.
- AUX Cloud or any other cloud backend, account login, external API credentials, and remote control outside the local network.
- IPv6, NAT traversal, VPN transport, and non-UDP transports.
- Automatic reset, unpairing, or deletion of device pairing data after authentication failure.
- Support claims for devices with a `devtype` other than `0x4E2a`.
- A dynamic capability-discovery protocol, because the specified discovery response does not provide a capability map.
- A custom `broadlink_ac.refresh` service.
- Per-entry temperature-unit configuration.
- Automatic persistence of raw packet captures or unredacted diagnostics.
- A promise that every listed brand, model, swing position, or switch function works on every physical device without live evidence.
- Cloud-only devices that cannot respond to the local protocol.
- Production deployment, HACS publication, or migration from an existing MQTT installation.

## Further Notes

- Before enabling this integration, the user must stop any existing MQTT bridge or other controller for the same air conditioner. Two controllers can authenticate independently and interfere with each other's session state.
- The most important unresolved evidence requirement is obtaining sanitized real response captures for authentication, states, and ambient data. Until those fixtures exist, parser tests and mock-UDP tests demonstrate behavior against the written specification, not complete hardware compatibility.
- The ambient protocol has two reference interpretations for the sensor-presence bit and fractional value. The selected v1 behavior is: if the presence bit is absent, return no ambient value; otherwise use the masked integer part plus the documented tenths value. The discrepancy must remain documented and be checked on live hardware.
- Unsupported vertical or horizontal swing requests may be normalized by the physical device to an off-like value. Such a response is not automatically an integration error.
- The repository currently has no glossary or ADRs. This specification uses the terminology established during design: config entry, coordinator, protocol layer, climate entity, switch entity, diagnostic entity, captured fixture, synthetic fixture, and live acceptance.
