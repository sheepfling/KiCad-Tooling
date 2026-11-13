# Malformed custom DRC condition fixtures

These tooling-owned KiCad version-1 `.kicad_dru` files cover malformed
argument shapes in one direct `(condition ...)` clause. Controls cover one
well-shaped expression, two repeated identical clauses, no condition clause,
and a text-variable expression. An absent condition is an unconditional rule;
multiple clauses are deliberately outside the lint predicate. No project or
cohort source is used.

The source hashes are:

| Fixture                                     | SHA-256                                                            |
| ------------------------------------------- | ------------------------------------------------------------------ |
| `control-repeated-condition.kicad_dru`      | `40f63575fede6e47995934b114be70046a1d3c0dd55994c3dbf327f8506af63f` |
| `control-single-condition.kicad_dru`        | `2d38c8202d0e7a3f6feab8ca06ce8ecdef0004a895e5a4e0e5a47b0e31f0ab5f` |
| `control-text-variable.kicad_dru`           | `56af7fad7626ea5350b7f7d5ff0d74495b3ce582deee069ea64d624d98284a62` |
| `control-unconditional.kicad_dru`           | `8c03637dc9704a1d0226bdd1f6707e7a0c319e503b6bb1c845e3951ef352aeb5` |
| `fault-empty-expression.kicad_dru`          | `45a83cc4be7959f612fa8bdafd56494bc5e25f6c5a3e88ee16a39af3aa501ce2` |
| `control-empty-quoted-expression.kicad_dru` | `7554451fe003a4b69952d8bae7f14fe35069cff7ad3ed24ac1b455b1cc9d28d2` |
| `fault-extra-condition-atom.kicad_dru`      | `df0af913fe32a0aa79c1ec6151da5d9b03d3486a099d96facff072558ec5e1b2` |

KiCad documents the condition clause as optional and describes one expression value for it in the
[KiCad 10 PCB Editor reference](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html). This lint checks
only that structural shape; it does not parse or evaluate the condition language.

The pinned KiCad 10.0.8 probe ran each case twice against the tooling-owned
synthetic two-track board. Single, repeated-identical, and empty-quoted
condition controls compiled, reached the terminal sentinel, and reported two
authored `track_width` findings. The no-expression and extra-atom faults failed
the probe, did not reach the sentinel, and reported only two unrelated
`track_dangling` warnings. Normalized violation signatures repeated exactly.
These observations apply to the tested source forms, fixture, and image; they
do not establish behavior for other condition expressions, board
configurations, or KiCad versions.
