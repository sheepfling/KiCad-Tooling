# Connector-only I2C SDA/SCL resistor-bridge fixtures

These tooling-owned schematics contain one explicitly identified connector
with complete native SDA/SCL pin metadata and one fitted 90 Ω resistor. There
is no on-board I2C controller. The fault connects the resistor directly
between the connector's separately assigned SDA and SCL nets; the control
places it across unrelated auxiliary nets. Both cases are expected to pass
ERC. The default-review heuristic asks whether the coupling is intentional;
it does not claim that the resistor is prohibited or that the connector pinout
is approved.

The native lane checks exact pin functions, complete net assignments, no ERC
errors, repeatable normalized netlists, source hashes, and the expected lint
result in digest-pinned KiCad 10.0.0 and 10.0.5 containers. These are synthetic
regression inputs and contain no product design source.

| Case    | Source              | SHA-256                                                            |
| ------- | ------------------- | ------------------------------------------------------------------ |
| Fault   | `fault.kicad_sch`   | `aefbc5b660faa3cd9ae88fb8cfda90cea53a0164f26664508fd7a34e78629bcc` |
| Control | `control.kicad_sch` | `46438f802cc997bdfc4b26d7e86be9d502a95cf5635bc4def21e089ab0045571` |

Run the focused rule and native-lane selections from the tooling checkout:

```sh
.venv/bin/python -I -m pytest tests/test_i2c_sda_scl_resistive_bridge.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.i2c_sda_scl_resistive_bridge")'

KICAD_RUN_NATIVE_I2C_SDA_SCL_RESISTIVE_BRIDGE_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_i2c_sda_scl_resistive_bridge_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.i2c_sda_scl_resistive_bridge")'
```
