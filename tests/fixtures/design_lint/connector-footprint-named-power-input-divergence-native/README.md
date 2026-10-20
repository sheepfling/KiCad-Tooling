# Footprint-alias named power-input divergence fixture

These tooling-owned synthetic schematics test
`connector.footprint_named_power_input_assignment_divergence`. Distinct
connector symbols share the same nonempty value, footprint, complete two-pin
inventory, and matching native pin metadata. Each pin 1 is `BIAS_IN` with
native `power_in` type. The fault assigns J1.1 and J2.1 to different nets;
pin 2 is a separate common anchor. The control assigns both power-input pins
to one net.

The rule asks for review only. Separate sources, switched rails, and isolated
power domains can be intentional; matching symbol properties and one common
anchor do not establish that the power inputs should be joined.

SHA-256 source digests:

- `fault.kicad_sch`: `d4dfd83d6e8c9859411e613b6f9313ae65efd25c33056541bf35b0e484b70aea`
- `control.kicad_sch`: `8b055617a737dde04b6647a7ce8f5e4a167aa9567b712a1b0d88696eae1f8a7c`
