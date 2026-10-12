# Named peer power-input all-open fixtures

These minimal tooling-owned synthetic schematics exercise
`component.peer_power_input_named_all_open` using native KiCad pin metadata.

| Fixture             | Case                                                          |
| ------------------- | ------------------------------------------------------------- |
| `fault.kicad_sch`   | Both fitted peers leave the matching `BIAS_IN` pin open.      |
| `control.kicad_sch` | Both peers assign `BIAS_IN` to the same synthetic `+3V3` net. |

The default-REVIEW heuristic asks an owner to review the common pattern. A
matching symbol, function, and native `power_in` type do not establish that the
pins must be connected. The rule does not infer intent from a net name and does
not create a required connectivity contract. Generic functions, recognized
supply/return roles, DNP peers, connectors, incomplete groups, mismatched
metadata, and ambiguous assignments are excluded or handled by specific checks.

Both files are synthetic, tooling-owned sources marked not for manufacture.
No project board or proprietary schematic was imported. The exact-version lane
exports each source repeatedly with the pinned KiCad 10.0.0 and 10.0.5 images
and compares source-bound normalized netlists.

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `07868167a3fcbe4a8e06a8f7fda29dbc73138808ada53e805db6cab4aa8909fc` |
| `control.kicad_sch` | `437224399056a521542a4ff556900b696250f3ad6d8fd6f7d66f24227c20d136` |
