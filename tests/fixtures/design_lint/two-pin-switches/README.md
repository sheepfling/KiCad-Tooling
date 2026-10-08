# Two-pin SPST switch fixtures

These synthetic schematics exercise `component.two_pin_switch_same_net`.
They contain no project board, bill of materials, or proprietary requirements.

| Source                         | Purpose                                                                              | SHA-256                                                            |
| ------------------------------ | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `same-net-spst.kicad_sch`      | Both pins of exact `Switch:SW_SPST` identity are on `SAME_NODE`; REVIEW is expected. | `1ddb2e72f4759c3edddd0f1c7077090c911fa3cbd36d48ef5a0850d6146c25b4` |
| `distinct-nets-spst.kicad_sch` | The two pins use separately named nets; no switch finding is expected.               | `2f9e43e716fe6bc89645734768ced5ff5491ba8b62330aa1c544db236d31e147` |

The embedded symbol uses the exact library identity and two passive native pin
numbers. Its simplified drawing is fixture-owned and makes no claim about a
part, footprint, switch state, or manufacturer symbol.

The native fixture lane exports each source twice with the digest-pinned KiCad
10.0.0 and 10.0.5 images. It compares normalized typed netlists and the lint
result. Netlist evidence does not prove physical switch state, footprint pin
mapping, assembled population, or PCB continuity.
