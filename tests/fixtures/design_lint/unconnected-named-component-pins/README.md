# Unconnected named component supply and return pins

These tooling-owned schematics verify native netlist evidence for named supply
and return pins on a non-connector component.

| Fixture                  | Assignment                      | Expected lint result                      |
| ------------------------ | ------------------------------- | ----------------------------------------- |
| `supply-fault.kicad_sch` | U1 VDD is open; GND is assigned | `component.unconnected_supply_pin` review |
| `return-fault.kicad_sch` | U1 GND is open; VDD is assigned | `component.unconnected_return_pin` review |
| `control.kicad_sch`      | U1 VDD and GND are assigned     | No finding from either named-pin rule     |

The embedded U1 symbol uses passive electrical types so this tests named
function recognition without relying on generic `power_in` evidence. The single
component cases avoid peer-comparison findings that could otherwise localize
the open pin. Separate exact-version lanes export each fault and the assigned
control twice on KiCad 10.0.0 and 10.0.5 and compare normalized netlist
evidence.

The review asks whether this named pin was intentionally left unused or a
connection is missing. It does not infer the required supply, correct rail,
voltage, source, ground domain, or physical copper path. These fixtures are
synthetic source-bound regressions, not a manufacturing design.

Reviewed schematic source SHA-256 values:

| Fixture                  | SHA-256                                                            |
| ------------------------ | ------------------------------------------------------------------ |
| `supply-fault.kicad_sch` | `f1ab42010ec4d41b3ea971e797a7cdff6c020fdaf86e7aae9e2f94664731d18e` |
| `return-fault.kicad_sch` | `43a421486e1ac8f138269128715a45e47fc1998a266d631c8461ffaaf58f9357` |
| `control.kicad_sch`      | `65e95e66fe3af0ce5136e5763f10f4b3aec71f658f790db929793a45c1895000` |

The focused pytest selectors are
`design_lint_rule(rule_id="component.unconnected_supply_pin")` and
`design_lint_rule(rule_id="component.unconnected_return_pin")`.

The supply-pin lane passed exact KiCad 10.0.0 and 10.0.5 hosted acceptance on
`v0.5.0rc158` (run `38252361023`). The return-pin lane's tagged acceptance is
also passed on `v0.5.0rc159` (run `38253423642`).
