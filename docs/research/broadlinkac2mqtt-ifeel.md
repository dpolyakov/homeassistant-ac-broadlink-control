# `broadlinkac2mqtt`: iFeel research

Date: 2026-10-29

## Question

Whether `ArtemVladimirov/broadlinkac2mqtt` contains a working iFeel command or
an additional temperature field that can be reused by this integration.

## Source

Repository revision checked: `b8586e9d527addb49ebff23ea51614d5486328b2`.

- [local backend](https://github.com/ArtemVladimirov/broadlinkac2mqtt/blob/b8586e9d527addb49ebff23ea51614d5486328b2/app/service/local.go)
- [service models](https://github.com/ArtemVladimirov/broadlinkac2mqtt/blob/b8586e9d527addb49ebff23ea51614d5486328b2/app/service/models/models.go)

## Findings

1. The project parses iFeel from the same field as this integration:
   `response.Payload[15] >> 3 & 1`.
2. It stores the parsed value in its raw state, but does not expose iFeel in
   `DeviceStatusHass` or in `DeviceCapabilities`.
3. Its full SET builder does not copy iFeel (and does not copy bit `FH`) into
   byte 15. Therefore it is not an implementation of iFeel control; it is a
   read-only observation that is not published to the user-facing state.
4. Its `ReadAmbient` request and decoder expose one ambient temperature using
   the same payload positions used here. There is no separate remote-control
   temperature field in this implementation.

The independent [AUX protocol description](https://github.com/GrKoR/AUX_HVAC_Protocol)
also documents byte 15 bit 3 (`iFL`) as the iFeel state and reports that Wi-Fi
control was not achieved, while the physical IR remote can enable it.

## Consequence for this integration

The external project does not provide a hidden command that fixes the observed
behavior. Our live captures already match its limitation: a full SET with
`iFL=1` is acknowledged, but the following state read can return `iFL=0`,
while the physical remote changes the state to `iFL=1`.

The safe contract is therefore:

- always parse and expose iFeel as read-only state;
- preserve the last read `iFL` and `FH` bits when building unrelated SET
  commands, so the integration does not clear them accidentally;
- do not claim a separate remote-temperature sensor until a distinct protocol
  field is captured;
- do not expose direct iFeel control until a device-specific Wi-Fi command is
  independently confirmed.

`FH` is a protocol-level observation from the external protocol description,
not a live observation from the current device. It must be parsed and tested
before being treated as a stable feature.
