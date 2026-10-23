# MOSFET terminal-order synthetic fixtures

These sources are small tooling-owned schematics marked `NOT FOR MANUFACTURE`.
They contain one synthetic gate-driven MOSFET each. The only case change is the
MOSFET channel family and the named drain/source rail assignments.

| Source | Channel | Drain | Source | Expected result | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| `fault_nmos.kicad_sch` | NMOS | `GND` | `+5V` | Opt-in review candidate | `b79b2a7bfde5855e43bf7abbed61f1d9954a576e88ffcc9c07a3d2f42953a81f` |
| `control_nmos.kicad_sch` | NMOS | `+5V` | `GND` | Quiet conventional-order control | `5b876b74b39d730820ae3d4cbb7d462874e0affa4a91add709db90c118154103` |
| `fault_pmos.kicad_sch` | PMOS | `+5V` | `GND` | Opt-in review candidate | `be3131997dc36fab36ab838dbafe52cb789838abab8a6a1e17aebe14de529a41` |
| `control_pmos.kicad_sch` | PMOS | `GND` | `+5V` | Quiet conventional-order control | `d5b4873bfcc1132c3940ebe112a5546ebc0a2820ad85c43655bf488fdac56e6a` |

The fixture lane exports the netlist and ERC report twice with the digest-pinned
KiCad 10.0.0 and 10.0.5 images. It checks stable normalized outputs, native pin
functions, the expected candidate on both fault cases, and no ERC errors.

This is a heuristic review of named-rail order, not a project requirement.
Back-to-back switching, reverse-current control, low-side PMOS, and other
topologies may intentionally use the reviewed orientation. The lane does not
validate the footprint pin map, transistor ratings, actual voltages, PCB copper,
or physical current direction.
