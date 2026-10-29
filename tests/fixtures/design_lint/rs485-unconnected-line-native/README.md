# RS-485 open A/B line regression

These are synthetic two-pin schematics created only to test the tooling. They
contain no product or cohort design data and are not manufacturing inputs.

Fault (`fault.kicad_sch`): a fitted, explicitly identified RS-485 transceiver
has A assigned to `RS485_A`; B has an explicit no-connect marker and no net
assignment. The rule reports the one-sided open line in its default review
mode.

Control (`control.kicad_sch`): the same pin inventory has A assigned to
`RS485_A` and B assigned to `RS485_B`; no finding.

The hosted runner pins each source SHA-256 and checks repeated netlist/ERC
exports using digest-pinned KiCad 10.0.0 and 10.0.5 images. These tests verify
the schematic-level review heuristic only; they do not establish PCB copper,
firmware use, or physical continuity.

Source hashes:

- `fault.kicad_sch`: `646edf03c83e0280e27ef7158872dc99e00890da0ddc3a7fce6ac65f1badf84d`
- `control.kicad_sch`: `41f8292b1cfe2e9487f7f14abbce16ddf26e187e9998feee52cfc9aaab919462`
