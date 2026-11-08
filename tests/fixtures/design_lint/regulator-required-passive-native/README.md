# Regulator required-passive native fixtures

These synthetic KiCad schematics exercise the mapped required-passive rule.
They contain no customer project data and are marked not for
manufacture in the title block.

- `control.kicad_sch`: C1 is fitted between the authored `REG_OUT` and `FB`
  nets.
- `alternate-control.kicad_sch`: C2 is fitted between those nets and matches
  the separately authored alternate population.
- `missing-passive.kicad_sch`: C1 is absent.
- `wrong-net.kicad_sch`: C1's second pin is assigned to `OTHER`.
- `wrong-pin-function.kicad_sch`: U1.2 keeps its pin number and `FB` net,
  while its native symbol function changes to `FB_ALT`.
- `wrong-pin-type.kicad_sch`: U1.2 keeps its pin number, function, and net,
  while its native electrical type changes from input to output.

The fixture test pins source hashes and exports each source twice with exact
KiCad 10.0.0 and 10.0.5 images. It requires stable netlists, clean ERC error
counts, no finding for either approved population, and the mapped review on
both faults.

The pin-role faults are controls for the existing component/net topology rule
and faults for `power.regulator_pin_role_mismatch`. They demonstrate that a
matching pin number and net can still disagree with explicitly authored native
function or electrical-type metadata. The fixture does not validate that the
authored metadata matches a real component datasheet.
