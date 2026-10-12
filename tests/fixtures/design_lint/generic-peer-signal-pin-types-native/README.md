# Synthetic generic connector signal-type matrix

These two tooling-owned schematics exercise every native signal electrical
type accepted by the opt-in `connector.generic_peer_pin_all_open` heuristic.
Both fitted connectors share a `+5V` anchor and an explicitly identified
`GND` return contact. The fault leaves one generic contact of each type open on
both peers; the control assigns each matching contact pair to its own net.

The native acceptance lane exports both cases twice on digest-pinned KiCad
10.0.0 and 10.0.5. It requires the observed pin type for `input`, `output`,
`bidirectional`, `tri_state`, `open_collector`, and `open_emitter` to match the
source and requires one review per open pin in the fault and no findings in the
control. Pin type narrows the peer comparison; it does not establish a required
connection.

| Fixture             | Signal contacts 2–7                           | Expected result              |
| ------------------- | --------------------------------------------- | ---------------------------- |
| `fault.kicad_sch`   | Unassigned on J1 and J2                       | Six opt-in `REVIEW` findings |
| `control.kicad_sch` | Each matching peer pair shares a distinct net | `PASS`                       |

## Source hashes

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `fbf954e97907913169d53491437423527c404795e1aeb4017ba4c3864c4acd02` |
| `control.kicad_sch` | `b59b67ba4f189afa4cf5e04e38ef54c748003ecde1195ab89d1f9cf52c51f22a` |
