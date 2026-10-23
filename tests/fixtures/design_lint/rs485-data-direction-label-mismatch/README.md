# RS-485 data-direction label fixtures

These Tooling-owned synthetic schematics exercise the bounded
`bus.rs485_data_direction_label_mismatch` review heuristic. The fault keeps the
RS-485 transceiver's driver-data input and receiver-data output on separate
native nets but assigns them to the opposite explicit UART1 TX/RX names. The
control uses matching labels. Passive pin types keep this predicate test
independent of ERC output-driver diagnostics.

| Source                                   | Purpose                                | SHA-256                                                            |
| ---------------------------------------- | -------------------------------------- | ------------------------------------------------------------------ |
| `crossed-data-labels.kicad_sch`          | D is on UART1_RX and R is on UART1_TX. | `10b0e622dd9359866b7edce3dd81c9f6bff6b7e00c3ce1392eef3ae5bb5f605a` |
| `matching-data-labels-control.kicad_sch` | D is on UART1_TX and R is on UART1_RX. | `16711f441b0a0fc050378ffea39b1bbcecf9c9c698a1da5987a15d5670327cad` |

The host-side role mapping follows documented pin functions: D/DI is the
transceiver driver-data input and R/RO is its receiver-data output. See the TI
[SN65HVD485E datasheet, Table 6-1][ti485] and Analog Devices
[MAX481/MAX485 family datasheet][adi485].
The native lane repeats netlist and ERC exports using digest-pinned KiCad
10.0.0 and 10.0.5 images. The heuristic does not establish a required system
connection, firmware behavior, PCB continuity, or off-board wiring.

Run the focused cases with:

```sh
.venv/bin/python -I -m pytest tests/test_rs485_data_direction_label_mismatch.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.rs485_data_direction_label_mismatch")'

KICAD_RUN_NATIVE_RS485_DATA_LABEL_MISMATCH_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_rs485_data_direction_label_mismatch_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.rs485_data_direction_label_mismatch")'
```

[ti485]: https://www.ti.com/lit/ds/symlink/sn65hvd485e.pdf
[adi485]: https://www.analog.com/media/en/technical-documentation/data-sheets/max1487-max491.pdf
