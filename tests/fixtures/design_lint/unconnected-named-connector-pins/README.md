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
| `supply-fault.kicad_sch` | `f65c87159f9e0c63b512afec4763e2468004402887836c31cf1048dec7b42ee1` |
| `return-fault.kicad_sch` | `b6c629d9da59acc5b5af27f383e56d6e4bb5e0a51c1077aa83ef1c17afd952b2` |
| `control.kicad_sch`      | `1fd0278dc65dc2a930fcd6d80ade89d0fa388679306067aef26ffa34dd0d14c3` |
