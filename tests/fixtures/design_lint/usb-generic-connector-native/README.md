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

The fixtures do not claim to represent a production connector or verify USB
behavior, reference policy, PCB copper, or physical continuity. The source
hashes are pinned in `kicad_tooling/ci_hosted_usb_generic_connector_cases.py`:

| Fixture                        | SHA-256                                                            |
| ------------------------------ | ------------------------------------------------------------------ |
| `fault.kicad_sch`              | `26940f23b66b4660365bd4a3c4e0cd821a29dcf8739c61d2f9277c262e1ffcc5` |
| `control.kicad_sch`            | `a4805756125893183c61278af060ba0cdcadf42180096335340431d0eef89a82` |
| `superspeed-fault.kicad_sch`   | `d630e21b270a371aa9674c7021f04b1dde1a449c481ec4216811b4d447a57f57` |
| `superspeed-control.kicad_sch` | `aa5c774319c88e32162462a0a32d8859a47a475b2bc75d1ede84f21d08087522` |
