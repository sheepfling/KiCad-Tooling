# Same-voltage split IC supply inputs

These tooling-owned schematics exercise the opt-in review for distinct native
`power_in` functions assigned to separate net names with the same explicit
nominal-voltage clue.

| Fixture             | U1 assignments                 | Expected target-rule result              |
| ------------------- | ------------------------------ | ---------------------------------------- |
| `fault.kicad_sch`   | VDD to `+3V3`; VDDIO to `3.3V` | REVIEW when the project enables the rule |
| `control.kicad_sch` | VDD and VDDIO to `+3V3`        | No target-rule finding                   |

This is a review heuristic, not an electrical requirement. It does not infer
actual voltage or claim that distinct supply pins should be joined. Intentional
filtering and separate supply domains remain valid. The exact-version native
lane checks the source-bound KiCad netlists on 10.0.0 and 10.0.5.

Reviewed source SHA-256 values:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `a83fb517ec8c31cd3c90ca31e1ecf117cf7397e273b659e6a928a32e44b21ce3` |
| `control.kicad_sch` | `3b9f69a92e9e46a574c3b4a54ec801995bd82867e24e706400021944deae69a3` |
