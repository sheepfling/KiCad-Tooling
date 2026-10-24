# I2C signal-label role fixtures

These are synthetic tooling fixtures with one two-pin I2C controller. The
role fault swaps the explicit `I2C_SDA` and `I2C_SCL` labels while retaining
both pin assignments. The named-rail fault assigns the native SDA pin directly
to `GND`. The control keeps the labels aligned with native SDA and SCL pin
functions.

| Case    | Source                           | SHA-256                                                            |
| ------- | -------------------------------- | ------------------------------------------------------------------ |
| Control | `correct-i2c-lines.kicad_sch`    | `c9129c01d99cc2636e2c1f5176fbf04cadc0ec875562ea83cc9f6dabe9ccf586` |
| Role fault | `mismatched-i2c-lines.kicad_sch` | `a9e9f961a03948608a2c36e2c7bf718003c8e3453f01593ce951ccdeb7d9774c` |
| Named-rail fault | `sda-on-ground.kicad_sch` | `a79212cd736bb83af906f7537cca72085fd190f7c5b1f0775b2fa9b4a4c476a9` |

The digest-pinned native lane exports all three schematics twice using the
exact KiCad 10.0.0 or 10.0.5 image declared by the regression, normalizes the
exported netlists, and checks the expected review findings. The lane validates
native export and analyzer repeatability; it does not establish hardware
intent or board routing.

Run the focused checks from the tooling checkout:

```sh
.venv/bin/python -I -m pytest tests/test_i2c_signal_label_roles.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.i2c_signal_label_role_mismatch")'

KICAD_RUN_NATIVE_I2C_SIGNAL_LABEL_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_i2c_signal_label_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.i2c_signal_label_role_mismatch")'

KICAD_RUN_NATIVE_I2C_SIGNAL_LABEL_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_i2c_signal_label_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.i2c_signal_on_named_rail")'
```

The schematics contain only synthetic symbols and labels. No product,
customer, or proprietary board source is included.
