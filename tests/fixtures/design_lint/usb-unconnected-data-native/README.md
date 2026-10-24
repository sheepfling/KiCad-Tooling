# USB 2.0 unassigned data-pin fixtures

These tooling-owned schematics exercise the opt-in review for an unassigned
native USB 2.0 D+/D− function. They contain no product design or project
expectation.

| Case              | Source                                                                                       | Expected result                                                                                                                        |
| ----------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Connected control | [`integrated-phy-direct.kicad_sch`](../usb-data-path-native/integrated-phy-direct.kicad_sch) | J1 and U1 D+/D− pins have native net assignments; no unassigned-data finding                                                           |
| Fault             | [`open-dp.kicad_sch`](open-dp.kicad_sch)                                                     | J1.1 D+ has an explicit no-connect marker while J1.2 D− remains assigned; the candidate is present with default `RULE_OFF` disposition |

The connected control SHA-256 is
`e93371b78de2ba8c473ccde0579e551d0da0b44b5d9ed417473ab1dd63781d27`. The
fault SHA-256 is
`86fcb43db0d885ee874ea8bc8d68387d808a1338248cacddded2591ec475079f`. The fault
changes only the J1 D+ connection from the shared data net to an explicit
no-connect marker; the PHY's D+ pin remains on the net.

The native lane repeats KiCad XML netlist exports, checks exact source hashes,
and verifies that the connected control is quiet while the open-pin fault is
reported without changing the rule's default-off policy. It runs under the
digest-pinned KiCad 10.0.0 and 10.0.5 USB polarity fixture gate. Generated
netlists and command receipts remain under ignored `build/` directories.

```sh
KICAD_RUN_NATIVE_USB_DATA_POLARITY_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q tests/test_usb_data_polarity_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.usb_unconnected_data_pin")'
```
