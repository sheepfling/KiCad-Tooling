# Synthetic repeated DB9 return-pin fixture

This fixture isolates one review question: four comparable connector peers
have different schematic net assignments on contacts numbered 7 and 9. The
control assigns each numbered contact to one shared net across all four peers.

The symbol is a tooling-owned two-contact abstraction. It models only the
generic contacts numbered 7 and 9; it does not reproduce a complete DB9
connector, any product design, or a board layout. The generic pin functions
keep the case within `connector.peer_pin_assignment_divergence`.

| Source              | SHA-256                                                            | Expected result                                          |
| ------------------- | ------------------------------------------------------------------ | -------------------------------------------------------- |
| `fault.kicad_sch`   | `0820a52afb270ec2380b64e645fb0b2ed855c656707c0325155ca9dba0fc525d` | Review pins 7 and 9 because each splits across four nets |
| `control.kicad_sch` | `0e5da68212518ba76a7643c19e339a540e759baff16c43193c37a6d428389122` | Pass this rule because each pin uses one common net      |

The native test exports each source twice with digest-pinned KiCad 10.0.0 and
10.0.5 images, computes each XML digest, then compares normalized typed
netlist contracts. Raw XML digests are not required to match between repeated
exports because serialization may include run-specific metadata.

This is a deterministic review heuristic, not a connectivity requirement.
Matching connector symbols and pin numbers do not prove that returns should be
bonded. The rule does not establish PCB copper connectivity or off-board
wiring, and the quiet control only means this particular heuristic has no
finding.
