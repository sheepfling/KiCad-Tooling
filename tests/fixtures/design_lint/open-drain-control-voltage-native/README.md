# Open-collector control pull-up voltage fixtures

These tooling-owned schematics exercise the open-collector control pull-up voltage-label review
with the native KiCad netlist exporter. They are synthetic, are not based on a product board, and
are not for manufacture.

- `fault.kicad_sch`: U1 and U2 are both supplied from `+3V3`; a fitted 10 kΩ resistor pulls their
  shared open-collector `CONTROL_SIGNAL` line to `+5V`.
- `control.kicad_sch`: the same topology pulls the line to `+3V3`, matching both endpoint supply
  labels and producing no finding.

The lane checks source hashes before and after export, requires KiCad 10.0.0 or 10.0.5 from the
selected public tooling template, runs the pinned container without network access, exports each
schematic twice, and compares normalized typed netlists. The fault must produce one finding with
the reviewed endpoint and resistor-path evidence; the valid control must remain quiet.

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `51338a18e26c6150e24a799d86c6333850e57c4ff67de94c1b07c5177482d5eb` |
| `fault.kicad_sch`   | `3305d61e5e888ff2addaad4d216245af276439476fc62b64542d9ff31ff5c515` |

Run the synthetic orchestration test with:

```sh
python -I -m pytest tests/test_open_drain_control_voltage_native_fixture_lane.py -m 'design_lint and interface_lint and power_lint'
```

The exact-version lane is selected with `KICAD_RUN_NATIVE_OPEN_DRAIN_CONTROL_VOLTAGE_FIXTURES=1`
and the `native_kicad` marker. Select this rule's complete gate with:

```sh
KICAD_RUN_NATIVE_OPEN_DRAIN_CONTROL_VOLTAGE_FIXTURES=1 python -I -m pytest tests/test_open_drain_control_voltage_native_fixture_lane.py -m 'design_lint and interface_lint and power_lint and native_kicad and design_lint_rule(rule_id="power.open_drain_control_input_pullup_voltage_review")'
```
