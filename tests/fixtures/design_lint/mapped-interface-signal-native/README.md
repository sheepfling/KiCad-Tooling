# Mapped interface signal native fixtures

These tooling-owned schematics exercise a two-pin generic UART connector.
The fault leaves mapped signal pin 2 unassigned; the control connects it to
`UART_RX`. Both include `UART_TX` on pin 1. They contain no project or customer
source.

Source SHA-256 values:

- `fault.kicad_sch`: `8d7cad1a7b1b0579890e0e2ad06af3b18f192f2a0ecf9260ebc3cae78c8c0554`
- `control.kicad_sch`: `634af7ee73a4cdbcc1a52967df2f08a0ca68b1a3100a8e13fef34225ef2eb6e1`

The exact-version native lane exports each source twice with the digest-pinned
KiCad 10.0.0 and 10.0.5 images, parses the native XML netlist, and evaluates the
same mapped-signal rule used by the synthetic tests. Run it with:

```sh
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 .venv/bin/python -I -B -m pytest -q \
  tests/test_connector_mapped_interface_signal_unassigned.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="connector.mapped_interface_signal_unassigned")'
```
