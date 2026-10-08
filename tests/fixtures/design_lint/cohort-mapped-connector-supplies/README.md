# Source-matched generic connector supply domains

These synthetic schematics test whether a reviewed interface map can surface a
split between generic connector supply pins that native symbol functions do
not identify.

| Fixture                           | Supply nets                                       | Return nets            | Expected native-only lint                                           |
| --------------------------------- | ------------------------------------------------- | ---------------------- | ------------------------------------------------------------------- |
| `split-supply-fault.kicad_sch`    | J1.1 uses `SUPPLY_ALPHA`; J2.9 uses `SUPPLY_BETA` | Shared `COMMON_RETURN` | `PASS`; generic `Pin_1` and `Pin_9` do not establish matching roles |
| `common-supply-control.kicad_sch` | J1.1 and J2.9 use `COMMON_SUPPLY`                 | Shared `COMMON_RETURN` | `PASS`                                                              |

The native regression then supplies a complete, digest-bound synthetic
interface catalog. With both power contacts reviewed as `supply` in the exact
same `external-5v` voltage domain, the split case returns `REVIEW` and names
both pins, native functions, catalog roles, and domain. The common-net control
returns `PASS`. Re-evaluating the split with J2's reviewed domain set to
`isolated-5v` also returns `PASS`; different authored domains do not form a
group.

This demonstrates incremental review coverage over native function matching.
The map does not prove a common connection is required. Independent sources,
power selection, ORing, switching, and isolation can be intentional. A
project-authored `pin_connectivity` requirement remains the authority for a
required relationship. The fixtures and catalog contain no customer or
proprietary source data.

Pinned native regression runs export each schematic twice on KiCad 10.0.0 and
10.0.5, compare normalized netlist contracts, and check source and export
evidence. The accepted mapped-return and mapped-supply results also require
the normalized native-netlist digests to match across both versions for the
split fault, common-net control, and distinct-domain control.

Reviewed schematic SHA-256 values:

| Fixture                           | SHA-256                                                            |
| --------------------------------- | ------------------------------------------------------------------ |
| `split-supply-fault.kicad_sch`    | `0991c6df2403df88ff33d5c359b14487b6aa385023bd864573ce236478449213` |
| `common-supply-control.kicad_sch` | `c45d390f138ebb9e440a1c6b0fea822f858ce9e31bfa229b28aaddc248adca3b` |

## Pinned cohort comparison (2026-10-05)

The deterministic analyzer in `aklofas/kicad-happy` was run directly from
commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, using
`--no-hierarchy --only-deterministic`, twice on each source. The fault report
contains `NT-001` INFO candidates for the singleton `SUPPLY_ALPHA` and
`SUPPLY_BETA` contacts; the common-net control has neither. Both reports say
`ground_domains.multiple_domains: false`. The fault also has a singleton
`CHASSIS` candidate, present in the control too. Generic ESD, datasheet,
sourcing, and lifecycle observations are outside this supply comparison.

The analyzer does not consume the interface catalog and does not relate these
two contacts through an authored voltage domain. Its singleton-net prompt is a
review clue, not evidence that the contacts must be common: valid off-board or
isolated supplies can also be singleton nets. The local mapped rule instead
names both reviewed supply roles and their shared `external-5v` domain, while
still leaving commonality to a project-authored connectivity requirement.

Repeated raw reports differ only in `inputs.run_id` and
`capability_mode_ref.run_id`. The canonical projection containing
`ground_domains` and the `NT-001` finding fields below is identical on repeat.
No candidate source or generated report was copied into the repository.

| Case           | First raw report SHA-256                                           | Repeat raw report SHA-256                                          | Stable projection SHA-256                                          |
| -------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| Split fault    | `d93950cb5eb40c2a80cb98c1d6a928d5440bd0cb07437d20325991e4c3150a3c` | `7077428d28d13f88be7d6bb38870aa4404605102f65669c9e5e2af3ddfd42842` | `6cdc099d451964f4fdf2845a0b9ed8578d8045b27488ea09ae9ea309f68c591f` |
| Common control | `1fc1abb6a0775c692e3c2571f921d9d000d564ae01a3b245af3036123a7daccf` | `d3d6d3577e9f98ff79bff8125128c56415c060cf8376a4807d3fe44e315a82`   | `e1fa9d45ccbeecb1591ef33bc69f4b76741f09e3cf99ac0c2e4dd0d2099f4509` |

Reproduction from the tooling repository root, with `HAPPY` pointing to a
checkout at the pinned commit and `OUT` outside source control:

```sh
python3.11 -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
  tests/fixtures/design_lint/cohort-mapped-connector-supplies/split-supply-fault.kicad_sch \
  --no-hierarchy --only-deterministic --output "$OUT/fault.json"
python3.11 -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
  tests/fixtures/design_lint/cohort-mapped-connector-supplies/common-supply-control.kicad_sch \
  --no-hierarchy --only-deterministic --output "$OUT/control.json"
```
