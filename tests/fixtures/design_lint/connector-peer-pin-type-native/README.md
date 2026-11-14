# Connector peer pin-type fixtures

These tooling-owned native schematics use two distinct connector symbols with
the same value, footprint, complete pin inventory, and pin functions. Both
assignments are common across the peers. The fault changes only J2 pin 2's
native electrical type from `passive` to `power_in`; pin 1 remains a common
metadata and net-assignment anchor. The control uses matching passive types.

The fixture supports a review prompt for inconsistent native alias metadata.
It does not establish which symbol type is correct, whether the ports are the
same interface, or whether the board copper is continuous. Exports repeat with
digest-pinned KiCad 10.0.0 and 10.0.5 images.

SHA-256 source digests:

- `pin-type-disagreement-fault.kicad_sch`:
  `29f037951c9e0367049ce5e9d56a07970979742984f30a5fbef7a36f9a5f8ad6`
- `pin-type-matched-control.kicad_sch`:
  `2a1b514077177c80405667e7b1acd64f22ea82c17877b199ec7d61065295cb60`
