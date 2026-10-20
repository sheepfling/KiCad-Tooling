# Footprint-alias named signal divergence fixture

This tooling-owned synthetic schematic tests the default-review rule
`connector.footprint_named_signal_assignment_divergence`. It has distinct
connector symbols with the same nonempty value, footprint, complete two-pin
inventory, and matching native pin metadata. Both pin 1 contacts are native
`output` functions named `UART_TX`, but J1.1 is assigned to `UART_TX_A` and
J2.1 to `UART_TX_B`. Pin 2 is a separate common-net anchor.

The rule asks for review only. Separate channel, port, switched, or isolated
signals can be intentional; the fixture does not assert that these nets should
be joined.

The native control reuses the source-bound common-net control from
[`connector-footprint-named-signal-output-native`](../connector-footprint-named-signal-output-native/README.md).

SHA-256 source digest:

- `fault.kicad_sch`: `2a63cd0836321ce6752b5b4725d830a7f96ad01533e903fe24dfae5b696084a1`
