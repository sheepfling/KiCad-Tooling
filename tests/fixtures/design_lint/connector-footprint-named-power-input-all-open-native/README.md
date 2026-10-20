# Footprint-alias named power-input all-open fixture

These tooling-owned synthetic schematics exercise
`connector.footprint_named_power_input_all_open`. Distinct connector symbols
share the same value, footprint, complete two-pin inventory, and matching
native pin metadata. Each pin 1 is `BIAS_IN` with native `power_in` type. The
fault leaves both `BIAS_IN` contacts unassigned while pin 2 remains a common
anchor. The control assigns both power-input contacts to one net.

The rule asks for review only. An input may be intentionally unused or
isolated; the fixture does not establish a required connection.

SHA-256 source digests:

- `fault.kicad_sch`: `fc7bf0d75bcc8775e39328d6e9cf0e19a2c244f3ac1b782fed9d95e23b30271d`
- `control.kicad_sch`: `8b055617a737dde04b6647a7ce8f5e4a167aa9567b712a1b0d88696eae1f8a7c`
