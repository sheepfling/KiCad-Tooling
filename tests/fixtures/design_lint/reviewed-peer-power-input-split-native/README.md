# Reviewed heterogeneous connector power-input fixtures

These tooling-owned, not-for-manufacture schematics exercise
`connector.reviewed_peer_power_input_split` with two distinct native connector
symbols, values, and footprints. Pin 1 is an unnamed native `power_in` contact;
the project-owned synthetic maps assign both contacts to `POWER_INPUT` in the
same `external-5v` domain and source-reviewed peer group.

| Fixture             | Schematic assignments                           | Expected lint result                 |
| ------------------- | ----------------------------------------------- | ------------------------------------ |
| `fault.kicad_sch`   | `J1.1=USB_5V`, `J2.1=SERIAL_5V`; pin 2 is split | REVIEW the distinct power-input nets |
| `control.kicad_sch` | Both pin-1 contacts use `+3V3`; pin 2 is common | No finding from this rule            |

The rule does not require joining these nets. The different sources may be
intentionally filtered, selected, or isolated. The native lane binds each
fixture source to its SHA-256 digest, exports it twice with the exact pinned
KiCad 10.0.0 and 10.0.5 images, and checks the normalized netlists and typed lint
results.

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `1f274d1f6358c0b4340e69473d582df0c5c843469930e0813eab7dad6b98bc4e` |
| `control.kicad_sch` | `d67e9657b9bcf7a8136d319c22562f2d6dcd4df11cc241dcd9613c18cc223110` |
