# Regulator required-passive native fixtures

These synthetic KiCad schematics exercise the mapped required-passive rule.
They contain no customer project data and are marked not for
manufacture in the title block.

- `control.kicad_sch`: C1 is fitted between the authored `REG_OUT` and `FB`
  nets.
- `missing-passive.kicad_sch`: C1 is absent.
- `wrong-net.kicad_sch`: C1's second pin is assigned to `OTHER`.

The fixture test pins source hashes and exports each source twice with exact
KiCad 10.0.0 and 10.0.5 images. It requires stable netlists, clean ERC error
counts, no finding for the control, and the mapped review on both faults.
