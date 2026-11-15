# Connector-only I2C missing pull-up fixtures

These tooling-owned schematics contain one connector exposing explicitly named
SDA and SCL pins, with no on-board controller. Both include 4.7 kΩ pull-up
resistors from the two signal nets to `+3V3`. The fault marks both resistors
DNP, so the default-review check reports the missing fitted paths. The control
fits both resistors and clears that finding.

The check is a review prompt, not a defect verdict. Internal and off-board
pull-ups are invisible in this netlist and can be valid; an exact project I2C
requirement can record and source-bind the approved topology. Repeated native
exports check the connector-only pins, net assignments, ERC, and lint result
using digest-pinned KiCad 10.0.0 and 10.0.5. No product source is retained.

| Case    | Source              | SHA-256                                                            |
| ------- | ------------------- | ------------------------------------------------------------------ |
| Fault   | `fault.kicad_sch`   | `3051b1072f50b8afd38fa82a7dc67985750cc7204819f6fac1aa84df2ee6cd9b` |
| Control | `control.kicad_sch` | `36d766c8293e5a865e8ec006022297e738be3404ec2cdaff42259cafc9f839a6` |

Run the focused synthetic and native regressions from the tooling checkout:

```sh
.venv/bin/python -I -m pytest tests/test_design_lint_i2c_missing_pullups.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.i2c_missing_pullup")'

KICAD_RUN_NATIVE_I2C_MISSING_PULLUP_CONNECTOR_FIXTURES=1 \
  .venv/bin/python -I -m pytest tests/test_i2c_missing_pullup_connector_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.i2c_missing_pullup")'
```
