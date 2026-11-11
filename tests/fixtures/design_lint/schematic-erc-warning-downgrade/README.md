# Schematic ERC Warning downgrade fixtures

These tooling-owned settings exercise the review prompt for a known KiCad
10.0 Error-default ERC rule explicitly changed to Warning. The control keeps
`pin_not_connected` at Error and an Error-exception rule,
`endpoint_off_grid`, at its KiCad Warning default. Native fixtures use the
separate tooling-owned `near-miss-pin-line.kicad_sch` schematic and compare
repeatable KiCad ERC reports in the pinned 10.0.0 and 10.0.5 images.

The prompt does not assert that an ERC violation exists or that the severity
choice is wrong. The default-severity key set follows KiCad's tagged
`erc_settings.cpp` and `erc_item.cpp`; see the sources linked in
`docs/DESIGN_LINT.md`.
