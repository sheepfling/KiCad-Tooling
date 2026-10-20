# Footprint-alias named power-output divergence fixture

These tooling-owned synthetic schematics test
`connector.footprint_named_power_output_assignment_divergence`. Distinct
connector symbols share the same nonempty value, footprint, complete two-pin
inventory, and matching native pin metadata. Each pin 1 is `BIAS_OUT` with
native `power_out` type. The fault assigns J1.1 and J2.1 to different nets;
pin 2 is a separate common anchor. The control assigns both power-output pins
to one net.

The rule asks for review only. Separate sources, switched rails, and isolated
power domains can be intentional; matching symbol properties and one common
anchor do not establish that the outputs should be joined.

SHA-256 source digests:

- `fault.kicad_sch`: `4c46589c7cd8b8ef9ec6db778b10c5f7200918b92dfb60c522208dcc24d243b9`
- `control.kicad_sch`: `ca350129168dc67fe71153a59a53d7901c92e413119798463cdca04d96e43482`
