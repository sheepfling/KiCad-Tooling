# Custom DRC malformed-bound fixtures

These tooling-owned KiCad version-1 `.kicad_dru` files exercise malformed or
unparseable bounds recognized by the shared parser. Faults cover a repeated
minimum, an unsupported length suffix, an unsupported constraint clause, and
a constraint with no explicit bound. Controls cover a valid range, a one-sided
minimum, and a text-variable substitution. No project design or cohort source
is used.

The source hashes are:

| Fixture                              | SHA-256                                                            |
| ------------------------------------ | ------------------------------------------------------------------ |
| `control-one-sided.kicad_dru`        | `4fe27356d07e7aebd839423fd4f07b8a52154697e23a2ac62cdbd1d9fb5573c6` |
| `control-text-variable.kicad_dru`    | `98a2044d062e9a8eb76486af2e630a9f8061ca469e7627b01d7bba6ae5e81634` |
| `control-valid-range.kicad_dru`      | `05c68a36ab8931368239f5063d2244df2950ededdd2cf2c69fa0cc76971cb594` |
| `fault-empty-constraint.kicad_dru`   | `932d9c3a6c9301b42024870fb3c619b95e858ae17d729fb01d4cce7212a0abf1` |
| `fault-invalid-length.kicad_dru`     | `73619520b432f80d0be5bbef3ed29c5b828ccc0b213137238400a9d121074b7e` |
| `fault-repeated-minimum.kicad_dru`   | `5ad574495d2fab8e2d08abf209742a8294cf257566bbd87248cad86db0638d9d` |
| `fault-unsupported-clause.kicad_dru` | `c740d8a8f8c1a2f492cf92ee8527dc90d81746dd7f88fe2419c47247bbf66212` |

The native compatibility probe combines the repeated-minimum and valid-range
rules with the tooling-owned synthetic two-track board and project settings
documented in
[`pcb-dru-contradictory-bounds`](../pcb-dru-contradictory-bounds/README.md).
On digest-pinned KiCad 10.0.8 both files completed DRC and yielded identical
reports: two `track_dangling` warnings. This shows only that the tested files
reached a repeatable report on that image and board. It does not establish
which duplicate bound KiCad uses or that the rule matched either track.
