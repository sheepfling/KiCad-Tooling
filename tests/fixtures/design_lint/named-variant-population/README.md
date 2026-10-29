# Named-variant population fixtures

These are tooling-owned synthetic sources for the named-variant DNP check:

- `variant.kicad_pro` declares `Synthetic Assembly A`.
- `board-u1-dnp.kicad_pcb` has that native PCB variant and marks U1 DNP.
- `board-fitted.kicad_pcb` has the same variant with U1 fitted.
- `../component-inventory-footprint-identity/control.kicad_pcb` has no named
  variant and is the fail-closed control.
- `build_variant_board.py` is the KiCad 10 `pcbnew` recipe used to generate the
  two PCB fixtures from the synthetic footprint-identity control board.

The native lane copies these fixed source files and the matching synthetic
schematics into temporary project directories. It exercises both DNP mismatch
directions, a fitted control, and a board that lacks the declared variant. It
also compares an explicit `pcb.required_fitted_reference` requirement against
the exact named-variant schematic netlist and board population exports. The
missing-variant case must block before default-variant exports are compared.
All inputs are synthetic; no customer, company, or project board is stored.

Fixture hashes:

- `variant.kicad_pro`: `c2e8cac912a1257972f849bae9f142a3ca771de283f4f37571bcf07c1c75fcb3`
- `board-u1-dnp.kicad_pcb`: `27441e0849367c46395e50350e608828dba742c4933571e52013400b33402107`
- `board-fitted.kicad_pcb`: `3d8b2a60b9f847a6a530acf1f146734c64c9437d600c6683c1123b1f13aead76`
- `../component-inventory-footprint-identity/control.kicad_pcb` SHA-256:
  `23a19d40848ad3b6136f163ccf3ab64c53fef9185d696cde96323b66415d8913`
