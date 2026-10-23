# Diode rail orientation fixtures

These small, tooling-owned schematics are synthetic tests only and are not for
manufacture. They contain one exact `Device:D` symbol whose native pin functions
identify `A` and `K`; the two rail labels are exchanged between fault and
control.

| Fixture             | Anode label | Cathode label | Expected result                                             |
| ------------------- | ----------- | ------------- | ----------------------------------------------------------- |
| `fault.kicad_sch`   | `+3V3`      | `+5V`         | `component.diode_anode_below_cathode_on_named_rails` review |
| `control.kicad_sch` | `+5V`       | `+3V3`        | No finding                                                  |

SHA-256:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `811b5eeaa973d5183ad849d0115cfe754f8902393bb95ca5869b7b91ef28a195` |
| `control.kicad_sch` | `3dee00e1841431bf4e09f59cea48616ffb5674664a0b213cdf15565cf5713183` |

Hosted acceptance exports native netlists and ERC twice with digest-pinned KiCad
10.0.0 and 10.0.5. The gate checks exact source hashes, normalized repeatability,
zero native ERC errors, and the expected fault/control finding difference.
These examples test predicate behavior, not diode requirement, current flow,
board copper, physical population, or hardware suitability.
