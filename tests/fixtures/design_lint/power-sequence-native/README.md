# Native power-sequence map fixtures

These three schematics are synthetic tooling fixtures marked not for
manufacture. The control and open-enable cases contain two embedded
`Synthetic:Regulator` symbols with exact pin numbers, footprints, and `PART_ID`
fields. The control assigns `U1.3` power-good and `U2.1` enable to `GOOD_A`. The
open-enable fault moves only `U2.1` to `FLOATING_ENABLE`; it remains assigned to
a native net, so the regression tests the authored dependency rather than an
unconnected-pin rule.

The `output-enable-cycle` case adds a third regulator. Its mapped stage
endpoints and declared `rail-b` to `rail-c` dependency are valid and acyclic,
while `U1.1` is on `RAIL_B` and `U2.1` is on `RAIL_A`. The two exact
output-to-enable assignments therefore form a cycle that is absent from the
declared dependency list. The linter reports one `REVIEW` with the two mapped
edges; the cycle detector does not classify regulators or infer pin roles.

The native lane exports each schematic twice through its selected
digest-pinned KiCad image, checks the exact KiCad version, parses the XML netlist,
compares canonical parsed-netlist hashes, and evaluates the project-authored
power-sequence map. The control passes. The open-enable fault returns one
`power.mapped_sequence_dependency_mismatch` REVIEW on `U2.1`; the output-enable
cycle returns one REVIEW on the mapped `rail-a`/`rail-b` output-to-enable cycle.
Fixture inputs are mounted read-only, networking is disabled, and generated
receipts are retained under ignored `build/ci-hosted/` directories.

This validates the schematic-to-netlist adapter, exact mapped endpoints, and
the mapped output-to-enable cycle prompt. A prompt requires an explicit map;
omitted stages and an absent map remain a coverage question. It does not test
ERC behavior, active enable polarity, startup timing, firmware, silicon, voltage
limits, external control, or physical rail behavior. The synthetic source notes
do not stand in for a project owner's reviewed sequence requirement.

## Fixture source hashes

| Fixture                         | SHA-256                                                            |
| ------------------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch`             | `f1104387c9208d6be6a608872ddc9425158b05572d351e4afbd80d72a2f447c3` |
| `open-enable.kicad_sch`         | `b093d3b7b7b57f7a8aa3e1fa86b4c7c6b3440ebc6c3ee5d5c4a15ee4818f99fb` |
| `output-enable-cycle.kicad_sch` | `da22daa43ad104bdce3e499d651c36b5a0ed6556cd75347a07eed5a21ea22c6d` |

## Exact-version native results

Both digest-pinned versions repeated the same canonical netlist hashes for all
three fixtures. Raw KiCad XML can vary between invocations; repeatability is
therefore asserted on the fully parsed, normalized `NetlistContract`.

| KiCad version | Pinned image digest                                                | Control canonical netlist SHA-256                                  | Open-enable canonical netlist SHA-256                              | Output-enable-cycle canonical netlist SHA-256                      |
| ------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| 10.0.0        | `9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3` | `e4b9ca04a5eb7cb6e29b34f73b42d7aa9498f202d0ae630009de35dbc5f8b6b2` | `934453318f41f492077143e323d3868e764c4f1fc4767ff9c0fe6da24b2df8f8` | `e9f2f38126eec145400026ade2451525a592fbbfe9d5c2a711a92d023ddd1a86` |
| 10.0.5        | `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` | `e4b9ca04a5eb7cb6e29b34f73b42d7aa9498f202d0ae630009de35dbc5f8b6b2` | `934453318f41f492077143e323d3868e764c4f1fc4767ff9c0fe6da24b2df8f8` | `e9f2f38126eec145400026ade2451525a592fbbfe9d5c2a711a92d023ddd1a86` |

The control reports lint `PASS` with no sequence finding on both versions. The
open-enable fault reports `REVIEW` with the mapped endpoint mismatch, and the
cycle case reports `REVIEW` with the output-to-enable cycle, on both versions.
