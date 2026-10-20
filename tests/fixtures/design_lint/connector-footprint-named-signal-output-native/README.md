# Footprint-alias named signal-output fixtures

These tooling-owned KiCad schematics exercise the default-review rule
`connector.footprint_named_signal_output_open_outlier`. Distinct synthetic
connector symbols share the same value, footprint, complete two-pin inventory,
and native pin metadata. Pin 1 is `UART_TX` with native `output` type; pin 2 is
a passive common anchor. The fault assigns J1.1 and leaves J2.1 open. The
control assigns both UART_TX contacts to one net.

The finding is only a review prompt. It does not establish that the contacts
share a role or must connect, and these sources are not based on a product
board or project expectation.

SHA-256 source digests:

- `fault.kicad_sch`: `338f674f9dab065e286b2c5a4495b7967c81947343ce1497fefec347666362c8`
- `control.kicad_sch`: `f072787dbd52dafcc5e2fd0728ed2bc4add23653d8b4978c7472aa658b660d8f`
