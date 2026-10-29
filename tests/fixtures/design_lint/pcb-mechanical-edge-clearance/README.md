# Courtyard-to-board-edge clearance

These are tooling-owned synthetic KiCad 10 PCB sources. The project rule
requires at least 1.5 mm between front courtyard geometry and `Edge.Cuts`.

- `fault.kicad_pcb` places J1's courtyard 0.5 mm from the board edge.
- `control.kicad_pcb` places the same courtyard 3 mm from the board edge.
- `board.kicad_dru` places an unconditional 2 mm ignored physical-clearance
  search-radius anchor before the exact rule that applies the 1.5 mm limit.

The native fixture lane runs KiCad DRC on both boards with the digest-pinned
KiCad 10.0.0 and 10.0.5 images. It verifies the named `physical_clearance`
rule produces a clearance violation only for the fault. A separate rule-order
test changes only the synthetic rule text: a later unconditional ignore
suppresses the finding, while the mapped rule last and an opposite-courtyard
ignore last both retain it when the unconditional search radius is 2 mm. A
0.1 mm unconditional radius causes the 0.45 mm fault to disappear even when
the ignored rule is earlier or restricted to the opposite courtyard; a 0.1 mm
unconditional physical-hole-clearance rule has the same effect, while a 2 mm
physical-hole-clearance rule provides a sufficient search radius. With no
unconditional rule, this fixture is detected on 10.0.5 but not 10.0.0. These
outcomes are limited to the pinned images and this synthetic geometry; the
fixture does not set a universal clearance or approve a mechanical design.
