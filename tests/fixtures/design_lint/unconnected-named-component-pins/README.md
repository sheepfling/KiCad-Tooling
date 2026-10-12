# Unconnected named component supply pin

These tooling-owned schematics verify the native netlist evidence for
`component.unconnected_supply_pin` on a non-connector component.

| Fixture                  | Assignment                      | Expected lint result                      |
| ------------------------ | ------------------------------- | ----------------------------------------- |
| `supply-fault.kicad_sch` | U1 VDD is open; GND is assigned | `component.unconnected_supply_pin` review |
| `control.kicad_sch`      | U1 VDD and GND are assigned     | No finding from the named supply-pin rule |

The embedded U1 symbol uses passive electrical types so this tests named
function recognition without relying on generic `power_in` evidence. The single
component case avoids peer-comparison findings that could otherwise localize
the open pin. The exact-version lane exports both files twice on KiCad 10.0.0
and 10.0.5 and compares normalized netlist evidence.

The review asks whether this named pin was intentionally left unused or a
connection is missing. It does not infer the required supply, correct rail,
voltage, source, ground domain, or physical copper path. These fixtures are
synthetic source-bound regressions, not a manufacturing design.

Reviewed schematic source SHA-256 values:

| Fixture                  | SHA-256                                                            |
| ------------------------ | ------------------------------------------------------------------ |
| `supply-fault.kicad_sch` | `f1ab42010ec4d41b3ea971e797a7cdff6c020fdaf86e7aae9e2f94664731d18e` |
| `control.kicad_sch`      | `65e95e66fe3af0ce5136e5763f10f4b3aec71f658f790db929793a45c1895000` |

The focused pytest selector is `design_lint_rule(rule_id="component.unconnected_supply_pin")`.
