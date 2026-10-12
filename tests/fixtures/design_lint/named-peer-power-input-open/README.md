# Named peer power-input open-assignment fixtures

These synthetic schematics exercise
`component.peer_power_input_open_assignment` using native KiCad pin metadata.

| Fixture             | Case                                                 |
| ------------------- | ---------------------------------------------------- |
| `fault.kicad_sch`   | U1 is assigned; U2's matching `BIAS_IN` pin is open. |
| `control.kicad_sch` | Both peers assign the pin to one synthetic rail.     |

The rule is a default-REVIEW heuristic. The shared symbol, pin function, and
native electrical type identify a comparison group; they do not establish that
the open pin is defective or that peer pins must share a net. Generic pin
functions and recognized supply/return names remain with their existing
specific checks.

Both files are tooling-owned synthetic sources marked not for manufacture. The
native fixture lane exports each source twice using the project's exact pinned
KiCad 10.0.0 and 10.0.5 images and compares the source-bound normalized netlists.
