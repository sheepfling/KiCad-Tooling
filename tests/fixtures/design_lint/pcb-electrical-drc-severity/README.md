# Electrical DRC severity fixtures

These tooling-owned KiCad 10.0 project-settings fragments cover explicit
Warning and Ignore overrides for the documented Error-default electrical
checks `creepage` and `starved_thermal`.

- `fault.kicad_pro` sets `creepage` to Warning and `starved_thermal` to Ignore.
  It should yield two source-bound review candidates.
- `control.kicad_pro` leaves both checks at Error while lowering unrelated
  core, DFM, and signal-integrity checks. It should yield no candidate for
  this rule.

The settings do not contain a board or project source. The rule reviews an
explicit severity override; it does not prove that a creepage constraint or
thermal-relief violation exists, inspect copper, or establish electrical or
manufacturing approval.
