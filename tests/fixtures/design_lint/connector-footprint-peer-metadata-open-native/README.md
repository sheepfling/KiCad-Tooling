# Synthetic connector peer metadata and open-assignment fixtures

These tooling-owned schematics cover the case where two connector aliases
share the same value, footprint, and complete pin inventory, but a known pin
role differs and one peer's target pin is explicitly open. A second pin is a
common-net anchor in the fault and has separate nets in the control.

| Fixture             | J1.1          | J2.1                | Pin 2                                       | Expected result           |
| ------------------- | ------------- | ------------------- | ------------------------------------------- | ------------------------- |
| `fault.kicad_sch`   | `UART_RX_NET` | Explicit no-connect | `COMMON_REFERENCE` on both                  | `REVIEW` for pin 1        |
| `control.kicad_sch` | `UART_RX_NET` | Explicit no-connect | Separate `REFERENCE_A` / `REFERENCE_B` nets | No finding from this rule |

The pin functions are `UART_RX`/`UART_TX`, and the electrical types are
`input`/`output`. Different roles can explain an intentional open. The rule
asks for review of symbol pinouts and project-authored requirements; it does
not establish that these connectors are interchangeable or that the open pin
must connect. The files are not derived from a product board and are not for
manufacture.

SHA-256 source digests:

- `fault.kicad_sch`: `e6b24ecc2ecbafb23410b23ba18fb34ae78537957e66d4425f59a9265c0c5ed4`
- `control.kicad_sch`: `b7f54dfda65d777fc3532f4debb4f399c405b4e34a6d3d3d50d86f655089c8a4`

The native regression lane repeats export with the exact KiCad 10.0.0 and
10.0.5 images:

```sh
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  tests/test_connector_footprint_peer_metadata_open_native_fixture_lane.py \
  -m 'design_lint and native_kicad and design_lint_rule(rule_id="connector.footprint_peer_pin_metadata_open_outlier")'
```

Generated reports and command receipts stay under ignored `build/` directories.
