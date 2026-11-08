# Synthetic generic connector on an RS-485 line pair

These tooling-owned schematics exercise
`bus.rs485_generic_connector_pair_review`. The fault uses generic connector
contacts J1.1 and J1.2 on the exact A/B nets of an explicitly identified
SN65HVD485 transceiver. Both fixtures leave J1.4, whose native function is
`GND`, unassigned. The fault finding must show that state as evidence; the
named A/B control stays quiet despite the same open contact. This tests
visibility without inferring that the ground contact must be connected.

The source files are hash-pinned in
`kicad_tooling/ci_hosted_rs485_generic_connector_cases.py` and exported twice
with digest-pinned KiCad 10.0.0 and 10.0.5 images. The fixture is synthetic and
is not a manufacturing design.

Run the unit selection with:

```sh
python -I -m pytest -q tests/test_rs485_generic_connector_pair_review.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.rs485_generic_connector_pair_review")'
```

The exact native lane uses
`KICAD_RUN_NATIVE_RS485_GENERIC_CONNECTOR_FIXTURES=1`.
