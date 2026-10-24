# I3C SDA/SCL same-net fixtures

These tooling-owned schematics contain one synthetic I3C controller with
explicit `I3C1_SDA` and `I3C1_SCL` pin functions. The fault places both pins on
`I3C_SHARED`; the control connects U1.1 (`I3C1_SDA`) to `I3C_SDA` and U1.2
(`I3C1_SCL`) to `I3C_SCL`.
Exact-version exports check the native pin functions, net assignments, repeat
stability, and ERC result on KiCad 10.0.0 and 10.0.5. The review remains
default-off because function names alone do not prove device use or establish
the intended topology.

| Case    | Source              | SHA-256                                                            |
| ------- | ------------------- | ------------------------------------------------------------------ |
| Fault   | `fault.kicad_sch`   | `9c65be1911ef729b3ae066a63807ff021d6f6d70ce29a33ac4c9f6fef74028bb` |
| Control | `control.kicad_sch` | `05bf8adab0a4f0d54d1667008ed72f2e45a9b4ed5a8593a8e988612b8a9287ec` |

Run the focused tests from the tooling checkout:

```sh
.venv/bin/python -I -m pytest tests/test_i3c_signal_same_net.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.i3c_sda_scl_same_net")'

KICAD_RUN_NATIVE_I3C_SDA_SCL_SAME_NET_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_i3c_same_net_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.i3c_sda_scl_same_net")'
```

All inputs are synthetic and contain no external project source.
