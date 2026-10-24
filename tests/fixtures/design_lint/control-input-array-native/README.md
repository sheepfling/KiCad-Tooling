# Synthetic control-input resistor-array fixtures

These tooling-owned schematics exercise the project-authored reset-bias array
map through KiCad's native XML netlist export. The control connects a mapped
RN1 channel between `RESET_N` and `+3V3`; the fault moves RN1.1 to
`RESET_WRONG` while leaving the controller input connected to `RESET_N`.

| Fixture             | Native array mapping                    | Expected local-bias check | Heuristic disposition             |
| ------------------- | --------------------------------------- | ------------------------- | --------------------------------- |
| `control.kicad_sch` | RN1.1 on `RESET_N`, RN1.2 on `+3V3`     | PASS                      | COVERED by the exact authored map |
| `fault.kicad_sch`   | RN1.1 on `RESET_WRONG`, RN1.2 on `+3V3` | FAIL                      | OPEN with the channel mismatch    |

The separate `control-inputs.json` binds U1.1 to the reset signal and maps RN1
by exact symbol, footprint, value, `PART_ID`, complete four-pin inventory, and
channel nets. Pins RN1.3 and RN1.4 have reviewed unused-channel reasons. The
authored 10 kΩ value and range are requirements tied to the synthetic part
identity; the native netlist does not verify the resistor array's internal
construction or measured resistance.

## Source binding

| Input                         | SHA-256                                                            |
| ----------------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch`           | `d3c43f45f26a33bbadf39e7532fa8f4876255c9044d2122e93c121ce5d1a19d1` |
| `fault.kicad_sch`             | `05a4ad290ccf3a05e4ad0bb467f0b4b44422244a2cf27a2bbc42b310e1d1ae58` |
| `control-inputs.json`         | `688a44b9b6d1c3a2eeb5df82438e9ebbd601b36c12206ecd7bfa92ef73b900e3` |
| Two-schematic source manifest | `ae4973be1a4be68573799ba222cd794fc16bf8539d8cf96a260c163782e8e486` |
| KiCad image                   | `ghcr.io/kicad/kicad:10.0.5`                                       |
| KiCad image digest            | `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` |

Both samples are registered in the digest-pinned KiCad 10.0.5
`KICAD_RUN_NATIVE_CONTROL_INPUT_FIXTURES` lane. The lane exports each source
twice, checks normalized typed-netlist repeatability, and evaluates the same
typed control-input service used by the project contract and heuristic report.
It does not run ERC/DRC or establish electrical approval or PCB continuity.
