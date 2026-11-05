# GPIO to control voltage review fixtures

These are small synthetic KiCad schematics used to check the GPIO-to-control-input voltage review
rule with the native KiCad netlist exporter. They are not product designs and are not for
manufacture.

- `fault.kicad_sch`: an output named `GPIO0` on `+5V` drives an `EN` input on `+3V3` across
  `CONTROL_SIGNAL`.
- `control.kicad_sch`: the same direct link uses `+3V3` at the output and `+5V` at the receiver, so
  the higher-source-rail heuristic stays quiet.

Run the synthetic unit slice with:

```sh
python -I -m pytest tests/test_gpio_control_input_voltage.py -m 'design_lint and interface_lint and power_lint'
```

The exact-version native lane is selected with `KICAD_RUN_NATIVE_GPIO_CONTROL_VOLTAGE_FIXTURES=1`
and the `native_kicad` marker.

Select only this gate with:

```sh
KICAD_RUN_NATIVE_GPIO_CONTROL_VOLTAGE_FIXTURES=1 python -I -m pytest tests/test_gpio_control_voltage_native_fixture_lane.py -m 'design_lint and interface_lint and power_lint and native_kicad and design_lint_rule(rule_id="power.gpio_to_control_input_voltage_review")'
```
