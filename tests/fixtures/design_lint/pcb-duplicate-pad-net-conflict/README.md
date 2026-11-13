# Conflicting same-numbered copper-pad fixtures

These tooling-owned boards each contain one synthetic footprint, J1, with two
copper pads both numbered `1`. The footprint explicitly enables
`duplicate_pad_numbers_are_jumpers`, so KiCad treats those pads as one
off-board-connected contact. The fault assigns the pads to `SIGNAL` and
`RETURN`; the control assigns both to `SIGNAL`. The source-matched schematic
pin inventory contains J1.1.

SHA-256:

- `fault.kicad_pcb`: `a5e967fdf823d1f8378c15a0120879597b2806bccbf69ab798efdf5e47a210fe`
- `control.kicad_pcb`: `5690052e7ef96d3980111092a2c983c4d6b944a510bacb9627ea7f389e422246`

The fault and control produce identical KiCad 10.0.0 and 10.0.5 DRC
violations and unconnected-item evidence: each has only the same missing
synthetic footprint-library warning and no unconnected items. This is a
bounded observation for these fixtures and pinned versions. The local lint
reports the conflicting pad assignments as REVIEW evidence; it does not
assert that the footprint, schematic, or fabricated board is electrically
approved.

The heuristic only considers repeated numbered copper pads whose number is
present in the current native schematic pin inventory for the same fitted
reference. Differing net assignments deserve review because the corresponding
schematic pin is one connection. Intentional editing artifacts, custom
footprint semantics, and source-only board exceptions still require project
review. No cohort source or project data is included.
