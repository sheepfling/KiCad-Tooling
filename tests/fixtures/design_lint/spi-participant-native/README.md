# Synthetic native SPI roster-coverage fixture

This synthetic KiCad schematic has two connected SPI-like ICs. Its embedded
pin names use the exact `SPI1_SCLK`, `SPI1_COPI`, `SPI1_CIPO`, and `SPI1_NSS`
aliases recognized by the review heuristic. The schematic is intentionally
independent of a project roster: source intent is supplied by each test case.
It contains no product design or proprietary source.

Fixture SHA-256:

`0c5d901b4dc70ccb3c3818bd8fdf002955a6322b814ac2e7f8bab086d47d5e06`

| Review case  | Project roster supplied to the shared lint service | Expected result                                                     |
| ------------ | -------------------------------------------------- | ------------------------------------------------------------------- |
| `unrostered` | No SPI roster                                      | `REVIEW` candidates for U1 and U2, with native pin and net evidence |
| `rostered`   | Exact controller U1 and peripheral U2 requirements | No SPI participant candidate                                        |

The rostered case is a valid contract control for the same native source. It
shows that native pin-function matches are suppressed after project-authored
membership is present. Neither result decides whether a particular physical
device should be on this bus or verifies PCB copper continuity.

## Direct digital-peer voltage coverage

The same native exports exercise LINT-061 on the mapped `U1.2` to `U2.2`
`SPI_MOSI` path. Both endpoint identities and pin/net assignments must match
the exported netlist before the voltage comparison runs. With the synthetic
controller's guaranteed high maximum at 3.3 V and the receiver's absolute
maximum at 3.6 V, the control passes with 0.3 V minimum margin. Setting only
the synthetic output-high maximum to 5.0 V creates the fault and fails with
−1.4 V margin. The pin map and exported schematic stay identical between cases;
the limits are explicit project requirements rather than values inferred from
the net or part names.

Both cases repeat through digest-pinned KiCad 10.0.0 and 10.0.5 exports. The
normalized typed-netlist hash remains
`d1cefc2039d806f764e961eec8cc3e355ed74030edb742eb95e426c5e0a453c8`; both
voltage reports repeat exactly on each version. The underlying schematic and
all contract values are synthetic tooling fixtures.

## Exact-version regression

The hosted native lane exports this source twice with the digest-pinned KiCad
10.0.0 and 10.0.5 images selected by the public `KiCad-Test` checkout. The
parsed native pin functions and normalized netlist must repeat exactly; the
unrostered and rostered cases then run through the shared typed lint service.
Raw exports, receipts, and report evidence remain under ignored `build/` paths.

Both versions preserve all eight prefixed pin-function names. The unrostered
case reports U1 and U2 as review candidates; the exact roster control has no
SPI participant finding. The normalized typed-netlist SHA-256 is
`d1cefc2039d806f764e961eec8cc3e355ed74030edb742eb95e426c5e0a453c8` on both
versions. The 10.0.5 raw XML includes a changing export field, so its two raw
file hashes differ while the normalized contract is identical.
