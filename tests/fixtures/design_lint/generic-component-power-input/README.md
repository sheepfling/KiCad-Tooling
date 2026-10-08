# Generic non-connector power-input fixtures

These synthetic KiCad schematics exercise `component.unconnected_power_input`
using native `power_in` pin metadata and generic numeric pin functions.

- `fault.kicad_sch` leaves U1.1 unassigned.
- `no-connect-fault.kicad_sch` marks the same unassigned pin explicitly
  no-connect, which can suppress the corresponding native ERC open-pin report.
- `control.kicad_sch` assigns U1.1 to `+5V`.
- `dnp-control.kicad_sch` leaves U1.1 open on a DNP component.

SHA-256:

| Fixture                      | SHA-256                                                            |
| ---------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`            | `40271ae0a6551c8c7209427b30e89d9a95267aa92765eaac1a5cdf65e1ffd1a1` |
| `control.kicad_sch`          | `67d6ad249e1caa2095b3a408457e6a1710fb9bb6ef7d8e5cb1fdcdd7710b43ec` |
| `no-connect-fault.kicad_sch` | `664e619ceaba71c27bd7acfaa0bb4563ab3203b33a03c564b2a8f7c6bdf4c4bd` |
| `dnp-control.kicad_sch`      | `3be52ef83ba54bf0f43bede043095afe42583319e9fd6fa19f17aba250cc3c81` |

The rule asks for review. `power_in` alone does not say whether the pin is a
positive supply or a reference, and it does not establish that the pin must be
connected. Named VCC/GND pins remain with the more specific named-pin checks;
connector candidates remain with `connector.unconnected_power_input`.

All source is tooling-owned synthetic test data and is not a manufacturing
design. The native fixture lane exports each schematic twice with the pinned
KiCad 10.0.0 and 10.0.5 images and compares canonical typed netlist evidence.
