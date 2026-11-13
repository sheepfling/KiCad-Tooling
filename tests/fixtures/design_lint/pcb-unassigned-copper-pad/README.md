# Unassigned copper pad fixtures

These tooling-owned synthetic boards contain two fault/control pairs. The
numbered pair differs only in J1 pad 2's net assignment. The unnumbered pair
has the same physical pad with an empty pad number. The schematic pin
inventory contains J1.1 only:

- `fault.kicad_pcb` gives the pad no net while pad 1 has `SIGNAL`.
- `control.kicad_pcb` assigns pad 2 to `RETURN`.
- `unnumbered-fault.kicad_pcb` gives the unnumbered pad no net while pad 1 has
  `SIGNAL`.
- `unnumbered-control.kicad_pcb` assigns the unnumbered pad to `RETURN`.

The REVIEW heuristic asks a person to confirm whether a mixed-net footprint's
unassigned copper pad is an intentional NC/mechanical contact or a missing
assignment. For unnumbered pads, evidence includes the copper-pad ordinal and
source line because no schematic pin number can identify it. The check does
not infer the pad's schematic role. The fixtures contain no product or cohort
project data.

Pinned KiCad 10.0.0 and 10.0.5 DRC emits the same synthetic footprint-library
warning for each fault/control pair and no unconnected-item findings. The pad
assignment or number change does not distinguish the native DRC reports.
