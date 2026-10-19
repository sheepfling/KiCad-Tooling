# Explicitly ignored custom DRC rule fixtures

These synthetic `.kicad_dru` fragments exercise recognition of a direct
`(severity ignore)` declaration.

- `fault.kicad_dru` has one ignored rule and one active rule. Only the explicit
  Ignore declaration should produce a review candidate.
- `control.kicad_dru` uses error, warning, and exclusion severities and should
  produce no candidate.

They contain no board or project data and are parser inputs, not native KiCad
acceptance evidence. A review finding records the author's suppression and
asks whether it is intentional; it does not claim the rule should be enabled.
