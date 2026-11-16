# USB asymmetric series path fixtures

These tooling-owned synthetic schematics exercise the review prompt for a
USB 2.0 D+/D− pair with a fitted series resistor on one line and a direct path
on the other. They contain no product or proprietary design source.

| Fixture                                                         | Topology                | Expected result                                                                        |
| --------------------------------------------------------------- | ----------------------- | -------------------------------------------------------------------------------------- |
| `one-sided-series.kicad_sch`                                    | R1 in D+; D− is direct  | One `bus.usb_unmapped_asymmetric_series` REVIEW when no exact endpoint map is supplied |
| `../usb-data-path-native/external-phy-series-control.kicad_sch` | R1 and R2, one per line | Quiet control                                                                          |

The synthetic fault source SHA-256 is
`836f7e8aabcfd52d4b0c2d3589c822eeaedc4afe2898846db81626c136a8b8fc`.
The native regression exports both schematics twice with digest-pinned KiCad
10.0.0 and compares the normalized typed netlists before evaluating the same
source-bound rule used by the rest of the USB peer analyzer.

Run the native fixture lane with Docker:

```sh
KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES=1 \
.venv/bin/python -m pytest -q tests/test_usb_unmapped_asymmetric_series_native.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.usb_unmapped_asymmetric_series")'
```

The report does not establish that asymmetric paths are defective, that the
resistor is electrically appropriate, or that the component conducts. An
exact current project endpoint map suppresses the prompt and leaves mapped
topology comparison to `bus.usb_data_path_mismatch`.
