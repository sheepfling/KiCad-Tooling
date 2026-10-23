# Serial TX/RX label mismatch fixtures

These Tooling-owned synthetic schematics exercise the bounded
`bus.serial_tx_rx_label_mismatch` review heuristic. The crossed fault keeps
USART1 TX and RX on separate native nets while assigning each an opposite
USART1 label. The control uses matching labels. The pins use passive types so
ERC does not replace the lint assertion with pin-driver findings.

| Source                              | Purpose                                       | SHA-256                                                            |
| ----------------------------------- | --------------------------------------------- | ------------------------------------------------------------------ |
| `crossed-labels.kicad_sch`          | USART1 TX/RX pins use opposite role labels.   | `f48b576254795b7343c145478bf7e44380a7f1555def2c652d40570fa3c181f9` |
| `matching-labels-control.kicad_sch` | USART1 TX/RX pins use matching role labels.   | `912e346b5e745d60595eaae0715ccf9bc380bac34dd1ed047631ec4ea03b29d0` |

The native lane repeats KiCad XML netlist and ERC exports using digest-pinned
KiCad 10.0.0 and 10.0.5 images. The rule does not establish the authoritative
pin map, endpoint naming convention, protocol behavior, PCB copper, or
off-board wiring.

Run the fast and native cases with:

```sh
.venv/bin/python -I -m pytest tests/test_serial_tx_rx_label_mismatch.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.serial_tx_rx_label_mismatch")'

KICAD_RUN_NATIVE_SERIAL_TX_RX_LABEL_MISMATCH_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_serial_tx_rx_label_mismatch_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.serial_tx_rx_label_mismatch")'
```
