# Open CANH/CANL line native fixtures

These minimal schematics are synthetic tooling regressions. They use one
tooling-authored transceiver symbol and contain no product-board material.

- `control.kicad_sch` (SHA-256
  `79e2f1512c05cb291a8a542c2701d9737e8b0231d8790fcac7b33a89385c9e97`):
  U1.1/CANH and U1.2/CANL each have a distinct assigned signal net; no
  open-line finding.
- `fault.kicad_sch` (SHA-256
  `c84f251d9d84da280d75563a948b499af0b733d78167517106b0bcba9bb823e6`):
  U1.1/CANH is explicitly unconnected while U1.2/CANL remains assigned; review
  U1.1.

The native gate exports each source twice using digest-pinned KiCad 10.0.0 and
10.0.5 images. It checks exact pin functions, the open-pin inventory, repeated
normalized netlists, the lint result, and zero ERC errors. This validates only
schematic assignment for the recognized CANH/CANL names. It does not establish
that a pin is required, prove off-board continuity, or verify PCB copper.
