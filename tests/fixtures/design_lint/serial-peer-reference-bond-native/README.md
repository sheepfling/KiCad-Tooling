# Synthetic serial reference-bond fixture

This fixture checks the project-authored `bonded` reference policy for one
direct UART link. It is composed from synthetic symbols, labels, connector
instances, and a resistor. No product schematic, board, project expectation,
or proprietary design source was used.

The reviewed map names J1.3 on `GND_A`, J2.3 on `GND_B`, and one fitted
`Device:R` R3 with value `0R`, footprint `Synthetic:0603`, and passive pins
R3.1/R3.2. The control assigns the resistor pins to the corresponding endpoint
nets. The fault moves R3.2 to `FLOATING_GND`; the expected result is a failed
`serial/serial-bond/reference` check with the exact R3.2 assignment in its
detail. The map remains unchanged across both cases. J1.3 and J2.3 wires meet
the exported pin endpoints at `y=54.92` for symbols placed at `y=60`; the
control and fault differ only in R3.2's assigned net.

## Source hashes

| File                                      | SHA-256                                                            |
| ----------------------------------------- | ------------------------------------------------------------------ |
| `serial-reference-bond-control.kicad_sch` | `d6efb587268b8a0dcdbb90eb4401090dcbd6d254742b3e2f718d6df12591c785` |
| `serial-reference-bond-fault.kicad_sch`   | `a8a41b85d776f521df90998e55c5fc8eb55f1afc4839ab50d997b7a9e190aed2` |
| `serial-peer-map.json`                    | `0d224c8c6d59073902f21dee6ac9cdc6f7191b6659b6cff5bff437be65527c0b` |

## Native evidence

`serial_peer_reference_bond_fixture_lane` exports both schematics twice inside
the digest-pinned KiCad 10.0.0 and 10.0.5 images, compares repeated normalized
netlists, and evaluates the same typed `serial_peer_checks` service used by
electrical analysis. The native lane is registered in the GitHub serial-peer
acceptance job. A passing native export demonstrates the bounded schematic
contract behavior; it does not establish component conduction, PCB copper
continuity, external wiring, electrical suitability, or physical continuity.
