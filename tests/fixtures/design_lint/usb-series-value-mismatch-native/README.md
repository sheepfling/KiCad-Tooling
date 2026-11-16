# USB series-resistor value comparison fixtures

These tooling-owned KiCad schematics are a minimal fault/control pair for
`bus.usb_unmapped_series_resistor_value_mismatch`. The control is copied from
the tooling-owned `usb-data-path-native/external-phy-series-control.kicad_sch`
fixture. The fault changes only R2's placed `Value` from `27R` to `33R`.

| Case                | Source SHA-256                                                     | Expected result                                                                   |
| ------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| `control.kicad_sch` | `87e43a85255a91490cec5e1f8b101a9c408a45c855b9700a099cdc49ce27f01f` | Two native one-resistor paths with equal `27R` values; no value-mismatch finding. |
| `fault.kicad_sch`   | `78b5d5f31b9d4b7f19c836e6182acb910367a2312826e01d46bb950d1c3fe9a2` | D+ uses `27R`, D- uses `33R`; one default-REVIEW value-mismatch finding.          |

The native regression exports each source twice with digest-pinned KiCad
10.0.0 and 10.0.5 images in a network-disabled, read-only Docker container.
It compares repeated native netlists and checks the first-party review
predicate against the exact exported component values and pin-to-net paths.
The test establishes only those source/image outcomes. It does not establish
which value is correct, USB compliance, signal integrity, physical population,
or PCB copper continuity.

No cohort board, project source, or proprietary design data is included.
