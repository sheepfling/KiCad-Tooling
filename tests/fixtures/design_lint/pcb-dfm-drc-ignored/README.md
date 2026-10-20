# DFM DRC ignored-severity fixtures

These tooling-owned KiCad 10.0 project-settings fragments exercise review of
documented Error-default design-for-manufacturing checks explicitly set to
Ignore.

- `fault.kicad_pro` sets `hole_clearance` and `solder_mask_bridge` to Ignore,
  `track_width` to Warning, and keeps the remaining supported DFM checks at
  Error. It should produce two ignored-check candidates; the separate warning
  rule may report `track_width`.
- `control.kicad_pro` keeps all supported DFM checks at Error except for a
  Warning on `hole_clearance`. It also sets unrelated checks to Ignore and
  should produce no DFM ignored-check candidate.

The fragments contain no board or project source. Findings are source-bound
review prompts about configured severities; they do not establish that a DRC
violation exists or that every check must remain enabled.
