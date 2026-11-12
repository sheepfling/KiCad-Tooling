# Duplicate schematic ERC severity settings

These tooling-owned settings inputs contain the same key more than once under
`erc.rule_severities`. They are minimal synthetic JSON cases; no project board
or proprietary design source is included.

- `fault-ignore-last.kicad_pro` saves `warning` then `ignore` for
  `pin_not_connected`.
- `fault-warning-last.kicad_pro` reverses those values.
- `fault-unknown-duplicate.kicad_pro` repeats an unrecognized key.
- `fault-same-value-duplicate.kicad_pro` repeats an identical value.
- `control-unique.kicad_pro` has one valid `warning` entry.
- `control-duplicate-outside-map.kicad_pro` repeats a member elsewhere but
  keeps `erc.rule_severities` unique.

The exact KiCad 10.0.8 native lane uses the synthetic
`tests/fixtures/design_lint/near-miss-pin-line.kicad_sch` schematic. It measures
source-order behavior only for the known `pin_not_connected` key on that exact
image.
