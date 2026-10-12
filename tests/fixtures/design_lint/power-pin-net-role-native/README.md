# Named power-pin net-role fixture

This tooling-owned synthetic fixture tests a bounded name/function heuristic.
The embedded two-pin `Lint:PowerRoleComponent` has named `VDD` and `GND`
functions. Its native electrical types are passive so the fixture isolates
the design-lint predicate from ERC power-source rules.

| File                            | Intent                                                  | Expected result                        |
| ------------------------------- | ------------------------------------------------------- | -------------------------------------- |
| `fault.kicad_sch`               | `VDD` and `GND` are assigned to the net named `GND`     | Review `U1.1: VDD pin assigned to GND` |
| `control.kicad_sch`             | `VDD` is assigned to `+3V3`; `GND` is assigned to `GND` | No finding from this rule              |
| `negative-rail-fault.kicad_sch` | `VDD` is assigned to `-5V`; `GND` stays on `GND`        | Review `U1.1: VDD pin assigned to -5V` |

The digest-pinned hosted acceptance lane repeats KiCad 10.0.0 and 10.0.5
netlist exports and compares normalized source evidence for the common-return
fault/control and negative-rail fault/control cases. The latter is a review
candidate, not proof of electrical potential or project intent. A project
owner's pinout and power requirements remain authoritative. No product or
proprietary source is included.

Fixture source SHA-256 values:

| Fixture                         | SHA-256                                                            |
| ------------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`               | `ece15d4d36c6a9b72f7bda032736301e03f221e00f8b47c9e1542e01fd0b503e` |
| `control.kicad_sch`             | `b62f8049a7e7b9d271073694f521715c94fedf77cb9fff7b38256b5705cab225` |
| `negative-rail-fault.kicad_sch` | `70aa41e525c95cf9aab3252c71b497fd222d6ee9a0209113f18c08759c1c6141` |
