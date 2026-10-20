# DFM DRC warning-severity fixtures

These tooling-owned KiCad 10.0 project-settings fragments exercise review of
documented Error-default design-for-manufacturing DRC checks explicitly set to
Warning.

- `fault.kicad_pro` lowers `hole_clearance`, `solder_mask_bridge`, and
  `track_width` to Warning while keeping the other supported DFM checks at
  Error. It should produce three review candidates.
- `control.kicad_pro` keeps every supported DFM check at Error and sets
  unrelated checks, including documented Warning defaults, a core electrical
  check, and a signal-integrity check outside this rule, to Warning. It should
  produce no DFM candidate.

The fixtures contain no board or project source. A finding records the authored
severity and source hash; it does not claim a violation exists, that Warning is
unacceptable for a project, or that manufacturing approval has been established.
