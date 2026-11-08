# Reviewed connector peer group with an all-open generic contact

This tooling-owned schematic has two fitted, exact-symbol connector peers. Pin
1 is named `GND` and is open on both connectors. Pin 2 is a generic passive
contact and is also open on both. No pin provides a common-net anchor.

The native fixture validates the rule's bounded comparison behavior:

- A current source-reviewed peer group produces a default-off review prompt
  for the generic pin 2 contacts.
- Separate peer groups and no peer-group evidence remain quiet.
- The report retains both exact open contacts, the empty shared-anchor list,
  and the reviewed peer-group basis.

The peer grouping is review scope only. It does not establish that pin 2 is a
return or power contact, that it must connect, or that the ports should be
electrically common. A project-authored pinout and connectivity requirement
remain authoritative. The fixture does not represent any product board.

The source-bound native lane exports this schematic repeatedly using
digest-pinned KiCad 10.0.0 and 10.0.5 images.

SHA-256 source digest:

- `fault.kicad_sch`: `37fdbd5d0691e3bb44e6f8ef2b7cc4ee26e484f85a0c5160199f9b2f17e23cf3`
