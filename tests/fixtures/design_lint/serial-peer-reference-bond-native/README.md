# Synthetic serial reference-bond fixture

This fixture checks the project-authored `bonded` reference policy for one
direct UART link. It is composed from synthetic symbols, labels, connector
instances, and a resistor. No product schematic, board, project expectation,
or proprietary design source was used.

The reviewed map names J1.3 on `GND_A`, J2.3 on `GND_B`, and one fitted
`Device:R` R3 with value `0R`, footprint `Synthetic:0603`, and passive pins
R3.1/R3.2. The control assigns the resistor pins to the corresponding endpoint
nets. J1 TX and J2 RX use `SERIAL_A_TX`; J1 RX and J2 TX use `SERIAL_A_RX`.
The fault moves R3.2 to `FLOATING_GND`; the expected result is a failed
`serial/serial-bond/reference` check with the exact R3.2 assignment in its
detail. The map remains unchanged across both cases. J1.3 and J2.3 wires meet
the exported pin endpoints at `y=54.92` for symbols placed at `y=60`; the
control and fault differ only in R3.2's assigned net.

## Source hashes

| File                                      | SHA-256                                                            |
| ----------------------------------------- | ------------------------------------------------------------------ |
| `serial-reference-bond-control.kicad_sch` | `d6efb587268b8a0dcdbb90eb4401090dcbd6d254742b3e2f718d6df12591c785` |
| `serial-reference-bond-fault.kicad_sch`   | `a8a41b85d776f521df90998e55c5fc8eb55f1afc4839ab50d997b7a9e190aed2` |
| `serial-peer-map.json`                    | `db84fc9ef9ebbc019ccd5ced4ee0c8d686af201b9397375d658481caff58b6db` |

## Native evidence

`serial_peer_reference_bond_fixture_lane` exports both schematics twice inside
the digest-pinned KiCad 10.0.0 and 10.0.5 images, compares repeated normalized
netlists, and evaluates the same typed `serial_peer_checks` service used by
electrical analysis. The native lane is registered in the GitHub serial-peer
acceptance job. A passing native export demonstrates the bounded schematic
contract behavior; it does not establish component conduction, PCB copper
continuity, external wiring, electrical suitability, or physical continuity.

The local exact-version rerun on 2026-10-08 passed on both pinned images. The
control passed, and the fault failed only `serial/serial-bond/reference` in
both versions. The normalized control hash was
`5e530be356d5e584c8ad994eada95b8cfae78031145881890bcfb6cf690ffe80`; the
normalized fault hash was
`748d80edfe816b59c7b876f1d20a816f7de4652172e7e5d19c485f985965c20c`. Each
hash matched its repeated export and across KiCad versions. The raw commands and
exports are retained under ignored `build/ci/native-serial-peer-project-*/`
directories. This is local synthetic-fixture evidence; the current branch's
hosted acceptance has not run.
