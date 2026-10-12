# Named peer power-input assignment fixtures

These tooling-owned synthetic schematics exercise
`component.peer_power_input_named_assignment_divergence` using native KiCad pin
metadata.

| Fixture             | Case                                                                |
| ------------------- | ------------------------------------------------------------------- |
| `fault.kicad_sch`   | U1's `BIAS_IN` uses `SYNTHETIC_RAIL_A`; U2 uses `SYNTHETIC_RAIL_B`. |
| `control.kicad_sch` | Both peers assign `BIAS_IN` to `+3V3`.                              |

The default-REVIEW heuristic asks whether the split is intentional. A matching
symbol, function, and native `power_in` type do not establish that the nets
must be common. Generic pin functions and recognized supply/return roles stay
with their specific checks; open assignments stay with the named power-input
open-peer review.

Both source files are marked not for manufacture. The exact-version native
lane exports each source twice using the project's pinned KiCad 10.0.0 and
10.0.5 images and compares the source-bound normalized netlists.

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `0adf95fd2320f084c9475d896db2362c2b89123b303c01f3d83b2ebdffabe832` |
| `control.kicad_sch` | `89842c056127f07240df3e8dc812c8d89e04c1703a07dd247b450886d3b6c727` |
