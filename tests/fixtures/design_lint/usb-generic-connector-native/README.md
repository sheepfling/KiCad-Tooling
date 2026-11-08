# Generic USB connector coverage fixtures

These tooling-owned KiCad schematics test generic USB connector coverage for
USB 2.0 and direct USB SuperSpeed pairs. They use synthetic connectors and PHY
symbols. Data contacts are generic `Pin_N` functions in the fault fixtures and
explicitly named or incomplete in the controls.

| Fixture                        | Connector data functions | Expected result                                      |
| ------------------------------ | ------------------------ | ---------------------------------------------------- |
| `fault.kicad_sch`              | `Pin_1`, `Pin_2`         | One USB 2.0 generic connector review                 |
| `control.kicad_sch`            | `D+`, `D-`               | No USB 2.0 generic connector review                  |
| `superspeed-fault.kicad_sch`   | `Pin_1`, `Pin_2`         | One USB SuperSpeed TX generic connector review       |
| `superspeed-control.kicad_sch` | `Pin_1`, `Pin_2`         | No review; only one generic contact matches the pair |

The USB 2.0 fault fixture also includes an open VBUS contact and an assigned
USB ground contact. Its finding reports both contacts' native functions and
net state. This evidence does not require VBUS or ground to be connected.

The USB SuperSpeed fault now includes the same VBUS and GND contacts. Its
finding reports the open VBUS and the GND assignment from the exact native
export; the named-pair control remains quiet.

The fixtures do not claim to represent a production connector or verify USB
behavior, reference policy, PCB copper, or physical continuity. The source
hashes are pinned in `kicad_tooling/ci_hosted_usb_generic_connector_cases.py`:

| Fixture                        | SHA-256                                                            |
| ------------------------------ | ------------------------------------------------------------------ |
| `fault.kicad_sch`              | `26940f23b66b4660365bd4a3c4e0cd821a29dcf8739c61d2f9277c262e1ffcc5` |
| `control.kicad_sch`            | `a4805756125893183c61278af060ba0cdcadf42180096335340431d0eef89a82` |
| `superspeed-fault.kicad_sch`   | `b8d9f784e7aee88355510f62d402e2a706823085ab3a98822ae861d20b6a1b21` |
| `superspeed-control.kicad_sch` | `9997264ed1266c61e3012553fea8e25d3b50957548d35d5af706aea1e3cba1f1` |
