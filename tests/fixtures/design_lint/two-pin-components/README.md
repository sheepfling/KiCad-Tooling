# Synthetic two-pin component regressions

These schematics are tooling-owned synthetic fixtures. They contain no product
design or customer source.

| Fixture                                                          | Topology                                                 | Expected design-lint result                      |
| ---------------------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------ |
| `same-net.kicad_sch`                                             | Both resistor pins share one local label.                | `component.two_pin_passive_same_net` reports R1. |
| `distinct-nets.kicad_sch`                                        | Resistor pins use separate input and output labels.      | No same-net passive finding.                     |
| `custom-capacitor-same-net.kicad_sch`                            | Exact mapped custom capacitor pins share `+3V3`.         | `component.two_pin_passive_same_net` reports C1. |
| `../cohort-power-pin-dc/custom-capacitor-role-control.kicad_sch` | Same exact role-mapped capacitor spans `+3V3` and `GND`. | No same-net passive finding.                     |
| `same-net-diode.kicad_sch`                                       | Both diode pins share one local label.                   | `component.two_pin_diode_same_net` reports D1.   |
| `distinct-nets-diode.kicad_sch`                                  | Diode pins use separate anode and cathode labels.        | No same-net diode finding.                       |

Source SHA-256 values:

| Fixture                               | SHA-256                                                            |
| ------------------------------------- | ------------------------------------------------------------------ |
| `same-net.kicad_sch`                  | `54de8ccfcffb2d7e44a84fb4b5892872046bc963c2294242498d9b653d526a2b` |
| `distinct-nets.kicad_sch`             | `338deb4b9194e37a80813b3a3c447d21c14fa59fef78b0925898f595a27fbdea` |
| `custom-capacitor-same-net.kicad_sch` | `304c3eb9b979f807f99ee91fecec83e4688bb8d50207c298ff985688950e9fc2` |
| `same-net-diode.kicad_sch`            | `c7b34973f881f5c8d8e8ac26b07c03dec70b061f66b8338d61fb085583c2aa8b` |
| `distinct-nets-diode.kicad_sch`       | `74d19829e8dd9379a26cb6da9dd3cf10a48abce9d724661338f73ce0086bb928` |

The native fixture lane exports each source twice with the exact digest-pinned
KiCad 10.0.0 and 10.0.5 toolchains selected by the public acceptance projects.
It compares normalized native netlist contracts and the shared lint findings.
Run it with:

```sh
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 \
.venv/bin/python -I -m pytest -q tests/test_two_pin_component_native_fixture_lane.py -m native_kicad
```

The passive rule recognizes exact `Device:R`, `Device:C`, and `Device:L`
families. It also recognizes a custom capacitor only through a project-authored
role map matching `PART_ID`, symbol, footprint, and complete native pin
inventory. The synthetic mapped same-net fault and the existing exact-map
distinct-net control are exported twice by the native lane under the pinned
KiCad 10.0.0 and 10.0.5 toolchains, and are also covered by focused unit and
source-bound CLI/MCP tests. The diode rule recognizes
exact `Device:D` family symbols. Both rules require a complete, unambiguous
native two-pin inventory and exclude DNP parts. `Device:LED`, unmapped custom
symbols, and multi-pin devices are outside the diode predicate. A same-net
assignment can be intentional, so each rule defaults to review and does not
declare the topology electrically wrong.
