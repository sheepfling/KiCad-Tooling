# USB-C SBU named-rail synthetic fixtures

These two small schematics are tooling-owned synthetic fault and control
fixtures. They contain no project or product board data. The symbol functions
are `SBU1` and `SBU2` on both a generic connector and a fitted controller.

- `fault.kicad_sch`: the controller-side pins are assigned to `GND` and
  `+3V3`; both SBU pin functions request review.
- `control.kicad_sch`: the same pins use neutral `SBU1_BUS` and `SBU2_BUS`
  labels; the heuristic stays quiet.

Reviewed source hashes:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `65907be4e4d13ebae004f10dc74076ca350759a692dc614b1e9aa9166b907619` |
| `control.kicad_sch` | `ad15d977415856e97c8e701c653d20f26e9cc9d9751d662dcba0f459491fde87` |

The digest-pinned native lane exports each schematic twice with KiCad 10.0.0
and 10.0.5, checks normalized netlist repeatability, verifies the expected
assignments and review subjects, and requires zero ERC errors. This evidence
does not establish the intended SBU use, alternate-mode configuration,
electrical potential, passive-path behavior, PCB connectivity, or physical
continuity.
