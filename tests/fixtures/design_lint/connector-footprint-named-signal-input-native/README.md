# Footprint-alias named signal-input fixtures

These tooling-owned KiCad schematics exercise the default-review rule
`connector.footprint_named_signal_input_open_outlier`. Distinct synthetic
connector symbols share the same value, footprint, complete two-pin inventory,
and native pin metadata. Pin 1 is `UART_RX` with native `input` type; pin 2 is
a passive common anchor. The fault assigns J1.1 and leaves J2.1 open. The
control assigns both UART_RX contacts to one net.

The finding is only a review prompt. These synthetic sources do not establish
that the contacts share a role or must connect, and they are not based on a
product board or project expectation.

SHA-256 source digests:

- `fault.kicad_sch`: `faa41e1882b02ffe9ec3972855c93d63232d6a81ef22a1f21e0827c6ad4f35b4`
- `control.kicad_sch`: `2b5382a50608b644118693641ccbfd4280747d084550e9b5b0201449d2e2c620`
