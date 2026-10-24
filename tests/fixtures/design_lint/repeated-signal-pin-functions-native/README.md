# Repeated signal-function native fault and control

`fault.kicad_sch` is a tooling-owned IC with two input pins named `READY` on
separate schematic nets. `control.kicad_sch` keeps the same complete pin
inventory and joins those pins to one net. Both also include a distinct input
and a passive pin to exercise native function and electrical-type extraction.

The exact-version fixture lane exports each schematic twice with digest-pinned
KiCad 10.0.0 and 10.0.5 images, then requires the normalized netlist contract
and lint result to remain repeatable. The check asks for review of the split;
it does not declare that repeated pins must be tied.

Source SHA-256:

- `fault.kicad_sch`: `b03de491d57a86e201815bfbf6912d7c63a8619e8f7592367d53a4da472ef2fe`
- `control.kicad_sch`: `016f91ed152f01ff9bb0fcef924263984243a1a81c74d0a0647ebbd4e57d7e2d`

These fixtures contain no project or customer design source.
