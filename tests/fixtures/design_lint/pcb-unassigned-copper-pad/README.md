# Unassigned copper pad fixtures

These tooling-owned synthetic boards differ only in J1 pad 2's net assignment.
The schematic pin inventory contains J1.1 only, making the unassigned J1.2 an
extra footprint pad that the schematic-to-PCB pad comparison cannot classify:

- `fault.kicad_pcb` gives the pad no net while pad 1 has `SIGNAL`.
- `control.kicad_pcb` assigns pad 2 to `RETURN`.

The REVIEW heuristic asks a person to confirm whether the mixed-net footprint's
unassigned copper pad is an intentional NC/mechanical contact or a missing
assignment. It does not infer the pad's schematic role. The fixtures contain no
product or cohort project data.

Pinned KiCad 10.0.0 and 10.0.5 DRC emits the same synthetic footprint-library
warning for both boards and no unconnected-item findings. The pad assignment
change does not affect the native DRC report.
