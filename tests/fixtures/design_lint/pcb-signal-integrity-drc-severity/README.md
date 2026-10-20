# Signal-integrity DRC severity fixtures

These tooling-owned KiCad 10.0 project-settings fragments cover explicit
Warning and Ignore overrides for the five documented Error-default
signal-integrity DRC checks: `length_out_of_range`, `skew_out_of_range`,
`too_many_vias`, `diff_pair_gap_out_of_range`, and
`diff_pair_uncoupled_length_too_long`.

- `fault.kicad_pro` sets two checks to Warning and two to Ignore while leaving
  the fifth at Error. It should yield four source-bound review candidates.
- `control.kicad_pro` keeps all five checks at Error while setting unrelated
  core and DFM severities below Error. It should yield no candidate for this
  rule.

The settings do not contain a board or project source. The review records a
configured severity override; it does not determine whether a matching custom
DRC constraint applies, measure a route, or qualify signal integrity.
