# RS-485 A/B bus-line pins on named rails

These tooling-owned synthetic schematics exercise
`bus.rs485_line_on_named_rail`. Each source contains an explicitly identified
RS-485 transceiver and connector, each with a complete two-pin A/B inventory.
The fault assigns both A pins to `GND`; the control assigns both endpoints'
A/B pins to their respective `RS485_A` and `RS485_B` nets.

- `fault.kicad_sch` SHA-256: `df8e09f872f11cee4f17011eff4121bc41811458a0374f7662890bcbb9ddc810`
- `control.kicad_sch` SHA-256: `0629329bf9bb963b9e35c82f95100caa8d9bfe6570b0cd2ba171aea972f0e5e4`

The rule requires one exact A and B function, complete pin inventory, and
explicit RS-485 identity on an eligible fitted IC or connector. For connectors,
the symbol library ID or value must identify RS-485; generic A/B functions and
the SN65HVD23x CAN identity do not qualify. A rail-like label requests review
only; it does not prove that the connection is electrically wrong. Projects
can set the rule mode or record an exact reasoned ignore.

The exact-native lane repeats netlist and ERC exports with digest-pinned KiCad
10.0.0 and 10.0.5 images.

```sh
.venv/bin/python -I -m pytest tests/test_rs485_line_named_rail.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.rs485_line_on_named_rail")'

KICAD_RUN_NATIVE_RS485_LINE_NAMED_RAIL_FIXTURES=1 \
  .venv/bin/python -I -m pytest tests/test_rs485_line_named_rail_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.rs485_line_on_named_rail")'
```
