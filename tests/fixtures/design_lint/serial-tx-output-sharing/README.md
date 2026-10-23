# Serial TX output-sharing fixtures

These tooling-owned schematics exercise multiple fitted IC transmit functions
assigned to one native net. The fault ties two passive-typed `USART1_TX` pins
together. The control has one TX function feeding two RX functions. The passive
pin types keep the fault outside native ERC output-to-output diagnostics; the
heuristic provides a separate review clue for that gap.

| Case    | Source                               | SHA-256                                                            |
| ------- | ------------------------------------ | ------------------------------------------------------------------ |
| Control | `tx-one-to-two-rx-control.kicad_sch` | `2d49ca26d8a70d95c81b9b853b6bccca27a77d70e23b436a08c6b63574d98329` |
| Fault   | `tx-shared-fault.kicad_sch`          | `d9801df7bbe3ef1261dd1edc68cf1fa1adeb0b991412a67c108e2d2d216104b4` |

The exact-version lane exports each schematic twice and runs both netlist
analysis and ERC on digest-pinned KiCad 10.0.0 and 10.0.5 images. It requires
no ERC errors in either case, one lint candidate on the fault, and no candidate
when one transmitter feeds multiple receivers. This evidence validates the
synthetic gap and deterministic behavior; it does not establish real driver
behavior or whether a particular shared-transmit topology is valid.

Run from the tooling checkout:

```sh
.venv/bin/python -I -m pytest tests/test_serial_tx_output_sharing.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.serial_tx_outputs_share_net")'

KICAD_RUN_NATIVE_SERIAL_TX_OUTPUT_SHARING_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_serial_tx_output_sharing_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.serial_tx_outputs_share_net")'
```

All symbols and project names are synthetic. No product or proprietary design
source is included.
