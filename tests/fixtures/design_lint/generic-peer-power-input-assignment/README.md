# Generic peer power-input assignment fixtures

These synthetic schematics exercise
`component.peer_power_input_assignment_divergence` with native KiCad pin
metadata.

| Fixture             | Case                                                                                                                 |
| ------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `fault.kicad_sch`   | Two fitted U instances of the same exact native symbol have pin 1, a generic `power_in`, assigned to different nets. |
| `control.kicad_sch` | The same peers assign that pin to one common synthetic rail.                                                         |

Pin 2 is passive and shares a signal net in both sources. Pin 1's generic
function is intentionally roleless: the rule asks for review because matching
symbol identity and `power_in` type do not establish that separate rails must
be joined. The result does not prove a required rail relationship, physical
continuity, PCB connectivity, current capacity, or hardware behavior.

Both schematics are tooling-owned synthetic inputs marked not for manufacture.
The native lane exports each source twice with the exact project-pinned KiCad
10.0.0 and 10.0.5 images and compares normalized typed netlist evidence. The existing
`power.ic_rail_without_fitted_capacitor` heuristic also appears in both native
reports; the lane verifies that the new peer-assignment rule appears only for
the split-rail fault and does not count the independent capacitor review as a
peer-assignment finding.
