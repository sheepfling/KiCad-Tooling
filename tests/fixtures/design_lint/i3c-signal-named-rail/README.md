# I3C named-rail synthetic fixtures

These small schematics are tooling-owned synthetic fault and control fixtures.
They contain no project or product board data. Both include a generic
two-contact connector and a fitted IC with explicit `I3C1_SDA` and `I3C1_SCL`
native pin functions.

- `fault.kicad_sch`: the IC-side SDA pin is assigned to `GND` and SCL to
  `+3V3`; both assignments request review.
- `control.kicad_sch`: SDA and SCL use separate neutral bus labels; the
  heuristic stays quiet.

Reviewed source hashes:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `56764b6a7ba59ad5700876bb2a91959c7f7894fea0afdd778689d75beeba0bb4` |
| `control.kicad_sch` | `aa22ae02257335f0bbe756cfaf3b03ed35e86ad9f9b2659d8b54e15fb2b4fca9` |

The native lane exports each schematic twice with digest-pinned KiCad 10.0.0
and 10.0.5, checks normalized netlist repeatability, verifies the expected
assignments and review subjects, and requires zero ERC errors. These checks do
not establish intended bus topology, I3C use, passive paths, PCB connectivity,
or physical continuity.
