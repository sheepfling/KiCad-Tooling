# Reviewed peer power-output split fixtures

These synthetic schematics exercise
`connector.reviewed_peer_power_output_split`. They use unlike connector
symbols, distinct values and footprints, `power_out` pins named VBUS and
VDD_OUT, and separate authored output maps in one reviewed peer group.
`fault.kicad_sch` assigns the contacts to different nets;
`control.kicad_sch` assigns them to one common net.

The prompt remains REVIEW-only. A common interface signal and voltage domain
do not prove that separate outputs should be joined, and the netlist does not
prove PCB copper continuity. Both fixtures are tooling-owned and do not
reproduce a product schematic.

The native test exports both files twice with digest-pinned KiCad 10.0.0 and
10.0.5 Docker images, checks normalized netlist repeatability, then evaluates
the source-matched output maps.

SHA-256 source digests:

- `fault.kicad_sch`: `19b83b154efa06421f2b09874d2403ed708c848c2e75ac8ca042647eb146dce2`
- `control.kicad_sch`: `a3e5a9915ae3b3192730100e45835cb1ceb16606b380d286b06c0e2fbc83b380`
