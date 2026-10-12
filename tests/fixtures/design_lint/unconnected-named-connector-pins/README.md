# Unconnected named connector power pins

These tooling-owned schematics verify that native KiCad netlists preserve named
connector supply and return pins when they have no net assignment.

| Fixture                  | Assignment                        | Expected lint result                      |
| ------------------------ | --------------------------------- | ----------------------------------------- |
| `supply-fault.kicad_sch` | J1 VDD is open; GND is connected  | `connector.unconnected_supply_pin` review |
| `return-fault.kicad_sch` | J1 GND is open; VDD is connected  | `connector.unconnected_return_pin` review |
| `control.kicad_sch`      | J1 VDD and GND are both connected | No finding from either rule               |

The embedded connector symbol uses passive electrical types so the fixtures
exercise the named-function checks rather than ERC power-source rules. The
single-connector cases avoid peer-comparison findings that could otherwise
localize the same open pin. The exact-version lane exports each file twice on
KiCad 10.0.0 and 10.0.5 and verifies normalized netlist equality.

These are synthetic source-bound regressions. They do not determine whether a
particular real connector pin should be used, joined, bonded, or isolated; a
reviewed interface pinout remains the source of that requirement.

Reviewed schematic source SHA-256 values:

| Fixture                  | SHA-256                                                            |
| ------------------------ | ------------------------------------------------------------------ |
| `supply-fault.kicad_sch` | `e4f00aa22957dcdb152cc10a694b25ddeb2d442ed3cd6827bd2e9b2f6cf233aa` |
| `return-fault.kicad_sch` | `a9a76c8c9a1a01978b3c5ae3228825658631c4c9ad9cc5b73566427f5ce80a5f` |
| `control.kicad_sch`      | `ee2980cf387a0326ddb92bcbec8f562ca560c3a9cc9cc249075002148f1e2275` |
