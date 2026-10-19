# Core native DRC suppression fixtures

These small synthetic KiCad 10 project settings exercise the bounded check
`pcb.core_drc_check_ignored`.

- `fault.kicad_pro` sets only `unconnected_items` to `ignore`; it should produce
  one source-bound review candidate.
- `control.kicad_pro` keeps all five covered connection, shorting, and clearance
  checks active. It also includes ignored footprint and presentation checks
  that KiCad documents with Ignore defaults; those must stay quiet.

The checker reads `board.design_settings.rule_severities` from the exact
source-hashed `.kicad_pro`. The synthetic files contain no board or project
source. The finding asks for confirmation and does not claim the check should
be enabled or that the board is defective.
