# Generic connector power-output lint fixtures

These tooling-owned schematics test the review heuristic for fitted connector
pins with generic native `power_out` metadata and no exported net assignment.
The fixture does not represent a customer project or establish that an output
must be connected. An approved connector pinout remains the source of that
decision.

The fault schematic has two identical synthetic connector symbols. Their pin 1
functions are numeric placeholders, their native electrical types are
`power_out`, and neither receives a net. Their pin 2 contacts connect to GND.
The control assigns both pin 1 contacts to `+5V`. The rule should report only
the two open generic contacts in the fault, and no finding in the control.

The native lane exports both sources twice with digest-pinned KiCad 10.0.0 and
10.0.5 images, validates the exported pin types and assignments, and compares
normalized netlist digests. `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1` selects the
lane in hosted acceptance.

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `9e7f2de5fd90afc549f1ab1e54fa35593a2a4162f3ae2424d0c726ed4c727458` |
| `control.kicad_sch` | `cebc6a1a74b2a10dc2d56d7c79df3a14a74fd164e4da2a13183eb2668b862e9c` |
