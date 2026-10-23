# Courtyard-to-board-edge clearance

These are tooling-owned synthetic KiCad 10 PCB sources. The project rule
requires at least 1.5 mm between front courtyard geometry and `Edge.Cuts`.

- `fault.kicad_pcb` places J1's courtyard 0.5 mm from the board edge.
- `control.kicad_pcb` places the same courtyard 3 mm from the board edge.
- `board.kicad_dru` contains the exact source rule that applies the limit.

The native fixture lane runs KiCad DRC on both boards with the digest-pinned
KiCad 10.0.0 and 10.0.5 images. It verifies the named `physical_clearance`
rule produces a clearance violation only for the fault. The fixture does not
set a universal clearance value or establish a product's mechanical
requirement.
