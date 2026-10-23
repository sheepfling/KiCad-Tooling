# USB data pin/name polarity fixtures

These synthetic KiCad schematics check whether a recognized USB data pin
function agrees with the polarity named by its assigned net. They are not
product designs and contain no proprietary or customer source.

| Case    | Source                                                                                       | Expected result                                                                            |
| ------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Control | [`integrated-phy-direct.kicad_sch`](../usb-data-path-native/integrated-phy-direct.kicad_sch) | J1 and U1 D+/D− functions agree with their USB_D+/USB_D− net names                         |
| Fault   | `reversed-connector-pair.kicad_sch`                                                          | J1.1 D+ is assigned USB_D− and J1.2 D− is assigned USB_D+; pair completeness remains valid |

The fault changes only the two connector-side net labels in the control
schematic. Its SHA-256 is
`c3586926cfb20926b90160f7b9823fcb9e5c955a17c35babd450aca183c08c7e`.
The control source SHA-256 is
`e93371b78de2ba8c473ccde0579e551d0da0b44b5d9ed417473ab1dd63781d27`.

The native lane checks the selected project's exact KiCad version and
digest-pinned image, exports each source twice, parses the native XML into the
same netlist contract used by design lint, and requires repeatable normalized
evidence on KiCad 10.0.0 and 10.0.5. Generated netlists and command receipts
are stored under ignored `build/` directories.

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_USB_DATA_POLARITY_FIXTURES=1 \
.venv/bin/python -I -m pytest -q tests/test_usb_data_polarity_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.usb_data_polarity_label_mismatch")'
```
