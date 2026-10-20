# Footprint-alias named signal all-open fixtures

These tooling-owned synthetic schematics exercise the default-review rule
`connector.footprint_named_signal_all_open`. Distinct synthetic connector
symbols share the same value, footprint, complete two-pin inventory, and native
pin metadata. Pin 1 is `UART_TX` with native `output` type; pin 2 is a passive
common anchor. The fault leaves both UART_TX contacts unassigned. The control
assigns both contacts to one net.

The finding is a review prompt only. It does not establish that the contacts
share a role or must connect, and these sources are not based on a product
board, project expectation, or cohort export. The control source is shared with
the named signal-output fixture.

SHA-256 source digests:

- `fault.kicad_sch`: `694b9284e1e08d029ffaf6c69198bb20a3179c2f90896f32cbecf9040b687af1`
- `../connector-footprint-named-signal-output-native/control.kicad_sch`:
  `f072787dbd52dafcc5e2fd0728ed2bc4add23653d8b4978c7472aa658b660d8f`
