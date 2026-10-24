# Two-pin thermocouple same-net fixtures

These tooling-owned synthetic schematics cover
`component.two_pin_thermocouple_same_net` for exact `Device:Thermocouple`,
`Device:Thermocouple_Alt`, and `Device:Thermocouple_Block` identities. The
[official Device symbol library](https://kicad.github.io/symbols/Device.html)
lists those three identities as thermocouple symbols. Each synthetic embedded
symbol declares two passive pins numbered 1 and 2. The embedded drawings are
minimal test representations, not copied KiCad library graphics.

`same-net-thermocouples.kicad_sch` assigns both leads of all three identities
to one net per instance. `distinct-nets-thermocouples.kicad_sch` gives every
lead its own net. The fault and control are exported repeatedly by the native
KiCad 10.0.0 and 10.0.5 fixture lane. Those exports test the source-to-netlist
path and the lint behavior; they do not validate upstream library geometry,
temperature measurement, compensation, sensor grounding, PCB connectivity,
or physical wiring.

Run the focused synthetic check:

```sh
.venv/bin/python -I -m pytest tests/test_two_pin_thermocouples.py \
  -m 'design_lint and component_lint and design_lint_rule(rule_id="component.two_pin_thermocouple_same_net")'
```

Run the pinned native fault/control gate:

```sh
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_two_pin_thermocouples_native_fixture_lane.py \
  -m 'design_lint and component_lint and native_kicad and design_lint_rule(rule_id="component.two_pin_thermocouple_same_net")'
```
