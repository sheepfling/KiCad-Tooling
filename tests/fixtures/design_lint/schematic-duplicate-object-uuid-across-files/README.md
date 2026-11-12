# Duplicate schematic UUID across distinct files

This tooling-owned hierarchical schematic isolates one cross-file identity
collision. Two distinct child sheets each contain a wire object. The fault
assigns the second wire the first wire's UUID; the control gives the second
wire a unique UUID. Component references, pin UUIDs, connectivity, and sheet
paths otherwise match.

- `root.kicad_sch` (SHA-256
  `eea05c175b989ab23b3b6f550230f80205b35862505a49b7b81a62331c371b8a`) points
  to two different child files.
- `channel-a.kicad_sch` (SHA-256
  `002d7e5ecaf0dc814b16803aca6c5692057a5b6d6bc01e761c1e128954fa786c`) owns
  wire UUID `b0000000-0000-4000-8000-000000000005`.
- `channel-b-control.kicad_sch` (SHA-256
  `1958629fb6acff1d68d35d47465f6430edce71ec942161bbb6115490fd4c47e6`) uses
  its own wire UUID `e0000000-0000-4000-8000-000000000005`.
- `channel-b-fault.kicad_sch` (SHA-256
  `3002431de07044b11daea623b5f7d3ccd20a226ddce5d5920cfbcdbe798828d9`)
  repeats channel A's wire UUID.

The digest-pinned KiCad 10.0.5 native lane accepts the fault and control and
exports the same typed netlist. The rule reports the UUID collision across the
two source files with per-occurrence path, hash, line, and object-kind
evidence. This is a source identity review, not an electrical finding.

The separate [repeated-sheet fixture](../repeated-sheet/) confirms that one
child source referenced from two sheet paths is read once and does not produce
a cross-file collision. No cohort or proprietary project source is used.

Run the exact native regression with:

```sh
KICAD_RUN_NATIVE_SCHEMATIC_SYMBOL_INTEGRITY_FIXTURES=1 \
  .venv/bin/python -I -m pytest \
  tests/test_schematic_duplicate_object_uuid_native.py \
  -m 'design_lint and schematic_lint and evidence_lint and native_kicad and design_lint_rule(rule_id="schematic.duplicate_object_uuid")'
```
