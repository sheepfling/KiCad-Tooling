# Synthetic two-pin crystal regressions

These schematics are tooling-owned synthetic fixtures. They contain no product
design or customer source.

| Fixture                           | Topology                                                         | Expected design-lint result                                 |
| --------------------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------- |
| `same-net-crystal.kicad_sch`      | Both fitted crystal pins share `CRYSTAL_BYPASS`.                 | `component.two_pin_crystal_same_net` reports Y1 for review. |
| `distinct-nets-crystal.kicad_sch` | The two crystal pins use separate `XTAL_IN` and `XTAL_OUT` nets. | No same-net crystal finding.                                |

Source SHA-256 values:

| Fixture                           | SHA-256                                                            |
| --------------------------------- | ------------------------------------------------------------------ |
| `same-net-crystal.kicad_sch`      | `0a55a739bcce60cacafaadf2c9995c0ff3ef07caf4284745b420a8e0f2de2b1a` |
| `distinct-nets-crystal.kicad_sch` | `0c000075d25bc1da32b777367079d084f96fe8be88e258146b5796db99bbe39e` |

The native fixture lane exports each source twice with the exact digest-pinned
KiCad 10.0.0 and 10.0.5 toolchains selected by the public acceptance projects.
It compares normalized native netlist contracts and the shared lint findings.
Run it with:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 \
.venv/bin/python -I -m pytest -q tests/test_ci_hosted.py -k NativeTwoPinComponentFixtureTests
```

Recognition is limited to fitted exact `Device:Crystal` family symbols with a
complete two-pin native inventory and one unambiguous assigned net per pin.
Multi-pin crystal symbols, DNP parts, custom identities, incomplete inventories,
open pins, and ambiguous assignments are outside the predicate. A same-net
review prompt does not establish that the topology is wrong or that the crystal
oscillates; it does not prove footprint mapping, physical population, or PCB
copper connectivity.
