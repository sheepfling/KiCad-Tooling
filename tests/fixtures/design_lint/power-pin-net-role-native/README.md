# Named power-pin net-role fixture

This tooling-owned synthetic fixture tests a bounded name/function heuristic.
The embedded two-pin `Lint:PowerRoleComponent` has named `VDD` and `GND`
functions. Its native electrical types are passive so the fixture isolates
the design-lint predicate from ERC power-source rules.

| File                | Intent                                                  | Expected result                        |
| ------------------- | ------------------------------------------------------- | -------------------------------------- |
| `fault.kicad_sch`   | `VDD` and `GND` are assigned to the net named `GND`     | Review `U1.1: VDD pin assigned to GND` |
| `control.kicad_sch` | `VDD` is assigned to `+3V3`; `GND` is assigned to `GND` | No finding from this rule              |

The digest-pinned hosted acceptance lane repeats KiCad 10.0.0 and 10.0.5
netlist exports and compares normalized source evidence. The fault is a review
candidate, not proof of electrical potential or project intent. A project
owner's pinout and power requirements remain authoritative. No product or
proprietary source is included.
