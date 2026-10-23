# MOSFET drain/source same-net review fixtures

These tooling-owned schematics check one narrow native-netlist pattern for the
exact supported three-terminal MOSFET symbols. The review rule is opt-in and
does not establish that a same-net assignment is a design defect.

| Case    | Source                                    | Expected result                                                                        |
| ------- | ----------------------------------------- | -------------------------------------------------------------------------------------- |
| Fault   | `fault.kicad_sch`                         | Q1 drain and source use `S_NET`; `REVIEW` for `component.mosfet_drain_source_same_net` |
| Control | `../mosfet-gate-native/control.kicad_sch` | Q1 drain uses `D_NET` and source uses `S_NET`; no finding                              |

The fault schematic is based on the synthetic control source and changes only
the drain label from `D_NET` to `S_NET`. The checked source hashes are:

| Source                                    | SHA-256                                                            |
| ----------------------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`                         | `332cc8bef1c6af31e2e585f75824efa6a38049419f88e27071febebc2f07d3a4` |
| `../mosfet-gate-native/control.kicad_sch` | `e95ed1a5673723dc690e1fad27d534f3f834c371a489957c0c7050f642d18a75` |

The exact-version gate exports netlist and ERC evidence twice on the pinned
KiCad 10.0.0 and 10.0.5 images. The ERC export is checked for errors and
normalized hashes are compared across repeats. The fixture does not claim PCB
copper continuity, physical assembly state, MOSFET behavior, or electrical
approval.
