# Unmatched exact-reference custom DRC scope fixtures

These tooling-authored custom DRC rules exercise exact `A.Reference == '…'`
selectors against the synthetic J1 footprint from the shared
[courtyard-to-board-edge fixture](../pcb-mechanical-edge-clearance/README.md).
The board and project settings are reused directly so the fixture does not
duplicate generated KiCad source.

The `present` rule selects J1 and applies a 5 mm minimum edge clearance to its
pad. On the pinned KiCad 10.0.5 image, both `J1` and lowercase `j1` select the
footprint and produce the expected edge-clearance violation; the absent
`GHOST` selector does not apply. KiCad 10.0.0 does not apply this reference
condition in the same fixture. The lint is therefore enabled only for 10.0.5.

The sources are synthetic test data. An absent selector may be reserved for a
different board variant; the lint asks for review and does not assert that a
footprint should exist or that the board has an electrical defect.
