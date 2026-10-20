# Three-port USB peer-reference fixtures

These tooling-owned schematics add a third USB 2.0 hub channel to the native
peer-reference fixture. J1 and J2 use the hub's first two ports and share the
hub reference. The fault leaves only J3's port-3 return on a separate net; the
control places all three connectors and the hub on `BOARD_GND`.

The expected USB peer-reference result is one `REVIEW` for `J3 / U1`, port 3,
on the fault and no USB peer-reference findings on the control. The three exact
data paths must remain covered in both cases. Connector return policy remains
project-specific: the heuristic requests review and does not decide that the
separate reference is wrong.

| Fixture             | Reference assignments                             | Expected USB peer result    |
| ------------------- | ------------------------------------------------- | --------------------------- |
| `fault.kicad_sch`   | J1.4, J2.4, and U1.3=`BOARD_GND`; J3.4=`USB3_GND` | One review for J3/U1 port 3 |
| `control.kicad_sch` | J1.4, J2.4, J3.4, and U1.3=`BOARD_GND`            | No review                   |

Source SHA-256:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `2a4f7e61d8e3da0fa3be3c9717b7d04dcf3faf86778c11b7265653e32425cba5` |
| `control.kicad_sch` | `d2d5760a775c59fc8ab2ce10d9d765bea9620a7ec5c472fb9b0c6b4190d981d5` |

The digest-pinned USB native lane exports each source twice using KiCad 10.0.0
and 10.0.5. It verifies normalized netlist repeatability, all three mapped
data paths, the single-port fault localization, and the common-reference
control. The fixture contains no project or product source and is not a claim
about PCB copper or physical continuity.

The installed KiCad 10.0.6 CLI exported both fixtures twice locally. Each
normalized typed-netlist hash repeated; each authored data-path map matched all
three channels; the fault produced only the J3/U1 port-3 USB peer-reference
finding, and the control produced none. Normalized hashes were
`5d9c692a866f5be8bcaea25a1b8a0e17ad027d34283022b3d71048a7b5d59e72` (fault)
and `fbdfff8ac4a244c36374bcd728d76b98ce6999323156e69edad1b316c83a4bd8`
(control). Raw XML hashes changed across exports, so repeatability is evaluated
on normalized native netlist contracts.
