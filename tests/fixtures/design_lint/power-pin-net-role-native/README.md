# Named power-pin net-role fixture

This tooling-owned synthetic fixture tests a bounded name/function heuristic.
The embedded two-pin `Lint:PowerRoleComponent` has named `VDD` and `GND`
functions. Its native electrical types are passive so the fixture isolates
the design-lint predicate from ERC power-source rules.

| File                              | Intent                                                  | Expected result                        |
| --------------------------------- | ------------------------------------------------------- | -------------------------------------- |
| `fault.kicad_sch`                 | `VDD` and `GND` are assigned to the net named `GND`     | Review `U1.1: VDD pin assigned to GND` |
| `control.kicad_sch`               | `VDD` is assigned to `+3V3`; `GND` is assigned to `GND` | No finding from this rule              |
| `negative-rail-fault.kicad_sch`   | `VDD` is assigned to `-5V`; `GND` stays on `GND`        | Review `U1.1: VDD pin assigned to -5V` |
| `enable-return-fault.kicad_sch`   | `EN` is a native input assigned to `GND`                | Review the fixed enable-control state  |
| `enable-signal-control.kicad_sch` | `EN` joins the positive `+3V3` rail with `VDD`          | No finding from this rule              |
| `enable-vss-control.kicad_sch`    | `EN` is assigned to a `VSS`-prefixed label              | No finding; VSS may be a negative rail |

The digest-pinned hosted acceptance lane repeats KiCad 10.0.0 and 10.0.5
netlist exports and compares normalized source evidence for the common-return,
negative-rail, and enable-control fault/control cases. The enable review does
not infer control polarity or the actual electrical state. VSS-prefixed labels
are deliberately excluded. A project owner's pinout and power requirements
remain authoritative. No product or proprietary source is included.

Fixture source SHA-256 values:

| Fixture                           | SHA-256                                                            |
| --------------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`                 | `ece15d4d36c6a9b72f7bda032736301e03f221e00f8b47c9e1542e01fd0b503e` |
| `control.kicad_sch`               | `b62f8049a7e7b9d271073694f521715c94fedf77cb9fff7b38256b5705cab225` |
| `negative-rail-fault.kicad_sch`   | `70aa41e525c95cf9aab3252c71b497fd222d6ee9a0209113f18c08759c1c6141` |
| `enable-return-fault.kicad_sch`   | `69f5c34420fa5c28805e2b5f17950a06bdcd86979b21245076d829ae383a73c0` |
| `enable-signal-control.kicad_sch` | `6623e843b6e8d076e229583d55e88d639c39703dfa81cf4e7bc919e4bbec7f62` |
| `enable-vss-control.kicad_sch`    | `aad7c1d913edba11aee09867e5af3b404a0c9a1b62f243c70eee1534f64472a7` |
