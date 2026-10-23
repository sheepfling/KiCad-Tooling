# I2C SDA/SCL same-net fixtures

These tooling-owned schematics contain one synthetic I2C controller with
native SDA and SCL pin functions. The fault attaches both pins to
`I2C_SHARED`; the control assigns them to distinct `I2C_SDA` and `I2C_SCL`
nets. Exact-version native exports preserve the assignments and produce no
ERC errors on KiCad 10.0.0 and 10.0.5. The lint remains default-off because
pin-function names do not prove that a part implements standard I2C or that
the two pins must remain separate.

| Case    | Source              | SHA-256                                                            |
| ------- | ------------------- | ------------------------------------------------------------------ |
| Fault   | `fault.kicad_sch`   | `e45583f123b62fe0769d19e5ffd08200510b9abb44afb97d6a8fc269ed3e84b6` |
| Control | `control.kicad_sch` | `a6ef0cf9ed06fe027c53a4d57624b0a72d244de75e1266b8df0ded924e378681` |

Reproduce the focused checks from the tooling checkout:

```sh
.venv/bin/python -I -m pytest tests/test_i2c_signal_same_net.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.i2c_sda_scl_same_net")'

KICAD_RUN_NATIVE_I2C_SDA_SCL_SAME_NET_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_i2c_sda_scl_same_net_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.i2c_sda_scl_same_net")'
```

The fixture files are synthetic and include no external project source.
