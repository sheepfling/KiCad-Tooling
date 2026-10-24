# CAN excess-termination native fixtures

These tooling-owned schematic fixtures verify the `bus.can_excess_termination`
review heuristic using the normalized netlist exported by native KiCad.

- `control.kicad_sch` contains three synthetic CAN peers and two fitted direct
  120 Ω resistors across the recognized CANH/CANL pair. It must produce no
  excess-termination finding.
- `fault.kicad_sch` adds a third fitted direct 120 Ω resistor across the same
  pair. It must produce one review finding that identifies all three resistors.

Both sources are exported twice and compared after typed netlist normalization.
The exact-version lane is configured for the digest-pinned KiCad 10.0.0 and
10.0.5 images selected by the public template's `controller` and
`raspberry-pi-status-led` toolchains. Hosted runs must pass before the rule is
promoted beyond synthetic validation. This is a schematic heuristic
regression; it does not model physical bus endpoints, fitted assembly state
beyond the schematic's explicit DNP data, resistor tolerance, or PCB copper.

Reviewed source hashes:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `3baa84f1494dc7cdd8b4bef63aa1df792adccfbc8b429895b6d8fc1c45ed7`    |
| `fault.kicad_sch`   | `97f8f0b2feaff11d2a8dd73e6ccb0f4e8f745b5a550813728b703a7216d28756` |
