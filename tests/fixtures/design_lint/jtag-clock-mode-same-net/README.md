# JTAG TCK/TMS same-net fixtures

These tooling-authored schematics contain one synthetic fitted IC and exercise
the review-only JTAG clock/mode same-net heuristic. They do not describe a
product board.

- `fault.kicad_sch`
  - Result: U1 pins 1 (TCK) and 2 (TMS) share
    `JTAG_CLOCK_MODE_SHARED`; one REVIEW prompt.
  - SHA-256: `7b4cf2b56449a51ea5409de6091787eddcc7d0e83fa099313678b98e6f9c05b2`.
- `control.kicad_sch`
  - Result: U1 TCK and TMS have separate nets; no prompt.
  - SHA-256: `963cb4909133eb49b80c1dddeb8fa525ee5e56935687901b8870194401eb9fe4`.

The digest-pinned native lane checks exact pin functions and net assignments,
then repeats netlist and ERC exports on KiCad 10.0.0 and 10.0.5. The fixtures
must have no ERC errors and repeat-identical normalized netlists. This evidence
validates native export and bounded schematic review behavior; it does not
establish active JTAG, intended device configuration, or PCB copper continuity.
