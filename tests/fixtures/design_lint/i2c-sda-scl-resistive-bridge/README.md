# I2C SDA/SCL resistor bridge review fixtures

These tooling-owned schematics contain one fitted synthetic I2C controller and
one 90 Ω resistor. In the fault case the resistor directly bridges the
controller's separately assigned SDA and SCL nets. In the control case it
bridges two unrelated auxiliary nets. Both cases are expected to pass ERC; the
design-lint rule emits a configurable REVIEW only for the I2C bridge. A
purposeful resistor network can be valid, so the finding asks for review.

The native lane checks exact pin functions, complete net assignments, no ERC
errors, stable repeated normalized netlists, source hashes, and the expected
lint result against digest-pinned KiCad 10.0.0 and 10.0.5. These fixtures are
synthetic regression inputs and contain no product design source.

| Case    | Source              | SHA-256                                                            |
| ------- | ------------------- | ------------------------------------------------------------------ |
| Fault   | `fault.kicad_sch`   | `ba998932f011b666e95f21c4b4645998be840b780073749d5d7c3f2bc480914b` |
| Control | `control.kicad_sch` | `a1f6d89697b2727cb836c41687ade71f3e326fe3ae92e78a76b659d2a0520f69` |

Run focused checks from the tooling checkout:

```sh
.venv/bin/python -I -m pytest tests/test_i2c_sda_scl_resistive_bridge.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.i2c_sda_scl_resistive_bridge")'

KICAD_RUN_NATIVE_I2C_SDA_SCL_RESISTIVE_BRIDGE_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_i2c_sda_scl_resistive_bridge_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.i2c_sda_scl_resistive_bridge")'
```
