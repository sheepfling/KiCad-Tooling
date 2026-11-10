# Reviewed heterogeneous connector power-input fixtures

These tooling-owned, not-for-manufacture schematics exercise
`connector.reviewed_peer_power_input_split` and
`connector.reviewed_peer_passive_power_input_open` with two distinct native
connector symbols, values, and footprints. Pin 1 is a generic native
`power_in` or `passive` contact. Project-owned synthetic maps assign both
contacts to `POWER_INPUT` in the same `external-5v` domain and source-reviewed
peer group. The named-power extension maps `VBUS` and `VDD_IN` as supply roles;
their differing native function categories prompt review when their nets split.

| Fixture                        | Schematic assignments                               | Pin 1 type | Expected lint result                    |
| ------------------------------ | --------------------------------------------------- | ---------- | --------------------------------------- |
| `fault.kicad_sch`              | `J1.1=USB_5V`, `J2.1=SERIAL_5V`; pin 2 is split     | `power_in` | REVIEW the distinct power-input nets    |
| `control.kicad_sch`            | Both pin-1 contacts use `+3V3`; pin 2 is common     | `power_in` | No finding from this rule               |
| `passive-fault.kicad_sch`      | `J1.1=USB_5V`, `J2.1=SERIAL_5V`; pin 2 is split     | `passive`  | REVIEW the distinct power-input nets    |
| `passive-control.kicad_sch`    | Both pin-1 contacts use `+3V3`; pin 2 is common     | `passive`  | No finding from this rule               |
| `passive-open-fault.kicad_sch` | `J1.1=USB_5V`; generic passive `J2.1` is open       | `passive`  | REVIEW the open contact beside its peer |
| `named-fault.kicad_sch`        | `VBUS` and `VDD_IN` map to `USB_5V` and `SERIAL_5V` | `power_in` | REVIEW the split named supply contacts  |
| `named-control.kicad_sch`      | `VBUS` and `VDD_IN` both use `COMMON_5V`            | `power_in` | No finding from this rule               |

The rule does not require joining these nets. The different sources may be
intentionally filtered, selected, or isolated. The native lane binds each
fixture source to its SHA-256 digest, exports it twice with the exact pinned
KiCad 10.0.0 and 10.0.5 images, and checks the normalized netlists and typed lint
results.

| Source                         | SHA-256                                                            |
| ------------------------------ | ------------------------------------------------------------------ |
| `fault.kicad_sch`              | `1f274d1f6358c0b4340e69473d582df0c5c843469930e0813eab7dad6b98bc4e` |
| `control.kicad_sch`            | `d67e9657b9bcf7a8136d319c22562f2d6dcd4df11cc241dcd9613c18cc223110` |
| `passive-fault.kicad_sch`      | `08f4b355fce56952ed21bb63e39a20f4da061811ae7d7b791caef15786bd759e` |
| `passive-control.kicad_sch`    | `b05b1c46c0a492d6691261b905278eac431acd2c835dcc61e06d9d36a3d46223` |
| `passive-open-fault.kicad_sch` | `d6ca4949abb67e0a1b7f4e331a989808dcb215200b752503ba85e78f24645aa5` |
| `named-fault.kicad_sch`        | `ae825d986b42a4987d580d66a174fd87cf53d0c93d7d949ac65a3660990e1936` |
| `named-control.kicad_sch`      | `85dc5cb5f4458bc37efe8dba6f48064c72acf0c4987be0e4a8fde4b136e805f1` |
