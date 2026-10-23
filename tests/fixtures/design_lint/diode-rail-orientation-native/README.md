# Diode rail orientation fixtures

These small, tooling-owned schematics are synthetic tests only and are not for
manufacture. They contain one exact `Device:D` symbol whose native pin functions
identify `A` and `K`. The numeric fault compares `+3V3` with `+5V`; the return
fault compares `GND` with `+3V3`; the control reverses the latter orientation.

| Fixture                   | Anode net | Cathode net | Expected result                                             |
| ------------------------- | --------- | ----------- | ----------------------------------------------------------- |
| `fault.kicad_sch`         | `+3V3`    | `+5V`       | `component.diode_anode_below_cathode_on_named_rails` review |
| `fault-return.kicad_sch`  | `GND`     | `+3V3`      | `component.diode_anode_below_cathode_on_named_rails` review |
| `control.kicad_sch`       | `+3V3`    | `GND`       | No finding                                                  |

SHA-256:

| Fixture                   | SHA-256                                                            |
| ------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`         | `811b5eeaa973d5183ad849d0115cfe754f8902393bb95ca5869b7b91ef28a195` |
| `fault-return.kicad_sch`  | `a9d451916cdb836be6ad2b7f2561fc609827c3daabc9d6645190d34713442c33` |
| `control.kicad_sch`       | `98089723702153b63e9e8ce8ad67bf53277215ded30ad149dad6ef52330f78e4` |

Hosted acceptance exports native netlists and ERC twice with digest-pinned KiCad
10.0.0 and 10.0.5. The gate checks exact source hashes, normalized repeatability,
zero native ERC errors, and the expected fault/control finding difference.
These examples test predicate behavior, not diode requirement, current flow,
board copper, physical population, or hardware suitability.
