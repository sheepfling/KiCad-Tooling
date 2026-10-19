# Custom DRC exclusion-severity fixtures

These tooling-owned `.kicad_dru` fragments exercise source-bound recognition of
direct `(severity exclusion)` declarations.

- `fault.kicad_dru` has one warning rule followed by one excluded rule. Only
  the explicit exclusion should prompt review, with its one-based rule ordinal.
- `control.kicad_dru` uses error, warning, and ignore severities and should
  produce no exclusion-severity candidate.

They contain no board or project data and are parser inputs, not native KiCad
acceptance evidence. A review finding asks whether excluding matching
violations is intentional; it does not assert that an applicable violation
exists or that the custom rule should use another severity.
