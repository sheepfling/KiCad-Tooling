# Footprint-alias named power-output all-open fixture

This tooling-owned synthetic schematic exercises `connector.footprint_named_power_output_all_open`.
Distinct connector symbols share the same value, footprint, complete two-pin inventory, and matching
native pin metadata. Each pin 1 is `BIAS_OUT` with native `power_out` type. The fault leaves both
`BIAS_OUT` contacts unassigned while pin 2 remains a common anchor. The valid control reuses the
source-hashed common-net control from
[the power-output divergence fixture](../connector-footprint-named-power-output-divergence-native/README.md).

The rule asks for review only. An output may be intentionally unused or
isolated; this fixture does not establish a required connection.

SHA-256 source digests:

- `fault.kicad_sch`: `3a3b16f4b3c7441f326d0d0c3635f7b1f76891ffcd5e180a99ea6ebe019648ce`
- control: `ca350129168dc67fe71153a59a53d7901c92e413119798463cdca04d96e43482`
