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
detail. The map remains unchanged across both cases.

## Source hashes

| File                                      | SHA-256                                                            |
| ----------------------------------------- | ------------------------------------------------------------------ |
| `serial-reference-bond-control.kicad_sch` | `3d5a3a4e332fd4a4fbc4cc5387e8fc7f5aca37cc06f4c85e215cea296dd9e92e` |
| `serial-reference-bond-fault.kicad_sch`   | `d7517285b3106a2c3f895de8d8f24d782a844b8de388fce0492e9a26a4ab05f4` |
| `serial-peer-map.json`                    | `0d224c8c6d59073902f21dee6ac9cdc6f7191b6659b6cff5bff437be65527c0b` |

## Native evidence

`serial_peer_reference_bond_fixture_lane` exports both schematics twice inside
the digest-pinned KiCad 10.0.0 and 10.0.5 images, compares repeated normalized
netlists, and evaluates the same typed `serial_peer_checks` service used by
electrical analysis. The native lane is registered in the GitHub serial-peer
acceptance job. A passing native export demonstrates the bounded schematic
contract behavior; it does not establish component conduction, PCB copper
continuity, external wiring, electrical suitability, or physical continuity.
