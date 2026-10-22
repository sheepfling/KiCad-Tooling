# Synthetic connector peer with missing metadata and an open assignment

These tooling-owned schematics test a review heuristic for fitted connector
aliases with a complete matching pin inventory when native role metadata is
missing for a pin on one peer. Both use distinct symbols with the same value
and footprint. Pin 2 is the exact common-net anchor. Pin 1 is an input on both
symbols, while J2's function metadata is intentionally unnamed.

| Fixture             | J1.1 assignment | J2.1 assignment     | Expected result    |
| ------------------- | --------------- | ------------------- | ------------------ |
| `fault.kicad_sch`   | `UART_RX_NET`   | Explicit no-connect | `REVIEW` for pin 1 |
| `control.kicad_sch` | `SHARED_PORT`   | `SHARED_PORT`       | No finding         |

The matching metadata and common anchor are review clues. They do not prove the
symbols have interchangeable roles or that the open pin must connect. The rule
does not direct net joining or prove PCB copper or off-board continuity.

SHA-256 source digests:

- `fault.kicad_sch`: `ac23a42151b013689a6c90c66ba36da980f9798c670a553ab90983efb413e73e`
- `control.kicad_sch`: `ea9380576e3dd2aaa3710935c28c7b38b14399a5954ecc939d1538dd1722d0f0`

Both files were exported twice with the digest-pinned KiCad 10.0.0 and 10.0.5
images. Each version produced the same normalized netlist on repeated exports;
the fault prompted the rule and the control remained quiet. The fixtures
contain no product-board source and are not for manufacture.

Reproduce the exact-version lane with:

```sh
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  tests/test_connector_footprint_peer_missing_metadata_open_native_fixture_lane.py \
  -m 'design_lint and native_kicad and design_lint_rule(rule_id="connector.footprint_peer_pin_missing_metadata_open_outlier")'
```

Generated reports remain under ignored `build/` directories.
