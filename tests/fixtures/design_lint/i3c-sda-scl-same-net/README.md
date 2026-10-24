# I3C SDA/SCL same-net fixtures

These tooling-owned schematics contain one synthetic I3C controller with
explicit `I3C1_SDA` and `I3C1_SCL` pin functions. The fault places both pins on
`I3C_SHARED`; the control assigns them to separate `I3C_SDA` and `I3C_SCL` nets.
Exact-version exports check the native pin functions, net assignments, repeat
stability, and ERC result on KiCad 10.0.0 and 10.0.5. The review remains
default-off because function names alone do not prove device use or establish
the intended topology.

| Case    | Source              | SHA-256                                                            |
| ------- | ------------------- | ------------------------------------------------------------------ |
| Fault   | `fault.kicad_sch`   | `48a20d238dec4af201c15867d2c1d0064d5fa82e6f9ebcdf4cbbf452f657767b` |
| Control | `control.kicad_sch` | `60781c2942046cc85c0bc33e4317a5d2f411567c27d5e3e1407f8bc127c6ba6e` |

Run the focused tests from the tooling checkout:

```sh
.venv/bin/python -I -m pytest tests/test_i3c_signal_same_net.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.i3c_sda_scl_same_net")'

KICAD_RUN_NATIVE_I3C_SDA_SCL_SAME_NET_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_i3c_same_net_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.i3c_sda_scl_same_net")'
```

All inputs are synthetic and contain no external project source.
