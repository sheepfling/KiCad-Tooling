# Native USB-C duplicate-contact peer-reference fixtures

These tooling-owned KiCad schematics test `bus.usb_peer_reference_review`
against a synthetic USB-C-style contact group. J1 has two D+ contacts and two
D− contacts on their respective direct nets to synthetic PHY U1. D1 and D2
are complete two-pin passive, D-designated shunt branches from the data nets to
connector reference `USB_GND`. The fault assigns U1's AGND reference to
`PHY_GND`; the control puts both endpoint references on `BOARD_GND`.

The limited connector and diode symbols are synthetic fixtures. They are not a
USB-C connector pinout, USB implementation, protection design, or board.
No external schematic, board, generated netlist, or part data is included.

| Fixture             | Topology                                                                                                                  | Expected heuristic result                               |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `fault.kicad_sch`   | J1.A6/J1.B6 and J1.A7/J1.B7 share USB data nets with U1; D1/D2 shunt to `USB_GND`; J1 A1 and U1.3 use separate references | One review with every contact and branch pin identified |
| `control.kicad_sch` | Same direct contacts and branches; J1 A1 and U1.3 share `BOARD_GND`                                                       | No USB peer-reference review                            |

SHA-256 of the version-controlled schematic inputs:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `b07cb10e9467cb2e34d79cd5ce696a76d9feeb004f3ac218d4d2e0f27a3f510e` |
| `control.kicad_sch` | `456f8d1f23735db18f4ec1b0c347cc1ab1d396af3b957c40d9158e535015a70f` |

## Local native-export check

On 2026-10-07, KiCad CLI 10.0.6 exported both sources twice. Parsed native
contracts matched across each repeated export. The fault and control produced
the expected review/no-review results:

| Fixture | Normalized typed-netlist SHA-256                                   |
| ------- | ------------------------------------------------------------------ |
| fault   | `dd8f72049f006ca75bd10599136f3e5d8a9b53e5fa32303ada42d3562bef65da` |
| control | `7aef139a9d53ac0c67dcdebcee8a2062448be7355bf9b24f294ad10e68bcd8d1` |

The temporary exports and repeatability check remained under `/private/tmp`.
The digest-pinned KiCad 10.0.0/10.0.5 fixture job is wired through
`test_native_usb_data_path_fixture_lane_is_repeatable` in
`tests.test_usb_data_path_native_fixture_lane`; the exact-version job has not
run locally because Docker is unavailable. Hosted package acceptance for
tag `v0.5.0rc17` passed this fixture lane on both pinned versions in run
`37863872527`; the fault emitted one peer-reference review and the common
control stayed quiet. A local 10.0.6 export remains compatibility evidence for
that executable only.

The fixture validates schematic pin/net export and deterministic lint behavior.
It does not verify native ERC, actual connector construction, diode behavior,
PCB copper, reference bonds, physical grounding, or electrical suitability.
