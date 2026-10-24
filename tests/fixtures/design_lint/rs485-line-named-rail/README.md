# RS-485 A/B bus-line pins on named rails

These tooling-owned synthetic schematics exercise
`bus.rs485_line_on_named_rail`. The fault assigns the identified transceiver's
A line pin to `GND`; the control assigns A and B to separate `RS485_A` and
`RS485_B` nets. Both sources contain an explicit RS-485 identity and a complete
two-pin inventory.

- `fault.kicad_sch` SHA-256: `4e15a47d7418c3b17ae5cd2cf10cfcc6dc7e0ef796bbf9023aebbbe029ba6d1b`
- `control.kicad_sch` SHA-256: `ec8a53ce7ae539d233baf7952e773adb1911cd5d930c98f4b120d22b6865c4e3`

The rule requires one exact A and B function on an explicitly identified,
fitted integrated circuit. Generic A/B functions and the SN65HVD23x CAN
identity do not qualify. A rail-like label requests review only; it does not
prove that the connection is electrically wrong. Projects can set the rule
mode or record an exact reasoned ignore.

The exact-native lane repeats netlist and ERC exports with digest-pinned KiCad
10.0.0 and 10.0.5 images.

```sh
.venv/bin/python -I -m pytest tests/test_rs485_line_named_rail.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.rs485_line_on_named_rail")'

KICAD_RUN_NATIVE_RS485_LINE_NAMED_RAIL_FIXTURES=1 \
  .venv/bin/python -I -m pytest tests/test_rs485_line_named_rail_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.rs485_line_on_named_rail")'
```
