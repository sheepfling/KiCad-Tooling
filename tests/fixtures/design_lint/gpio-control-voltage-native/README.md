# GPIO to control voltage review fixtures

These are small synthetic KiCad schematics used to check the GPIO-to-control-input voltage review
rule with the native KiCad netlist exporter. They are not product designs and are not for
manufacture.

- `fault.kicad_sch`: an output named `GPIO0` on `+5V` drives an `EN` input on `+3V3` across
  `CONTROL_SIGNAL`.
- `lower-source-fault.kicad_sch`: the same direct link uses `+3V3` at the output and `+5V` at the
  receiver, prompting review of the receiver's input-high threshold.
- `control.kicad_sch`: the same direct link uses `+3V3` at both endpoints and stays quiet.

All three source files are synthetic and are checked by SHA-256 before exact-version export. Each
fault and the control are exported twice with KiCad 10.0.0 and 10.0.5.

| Fixture                        | SHA-256                                                            |
| ------------------------------ | ------------------------------------------------------------------ |
| `control.kicad_sch`            | `70184e5ab963e8e2afffbdaf6f803d4ebeae67e2a7d5cf0195e30439569d5454` |
| `fault.kicad_sch`              | `066861e84e4dfebeac615ee62b6207c411267ff13b828a033ab32a382ca56437` |
| `lower-source-fault.kicad_sch` | `8fbe7219de30483919845ad3d008d56e39e52c055db3d42a59b0b5c2e79727fe` |

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
