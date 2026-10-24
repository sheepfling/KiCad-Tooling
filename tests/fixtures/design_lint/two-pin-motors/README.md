# Two-pin DC motor same-net fixture

These tooling-owned schematics exercise `component.two_pin_motor_same_net`
using the exact `Motor:Motor_DC` library identity and a minimal synthetic
two-pin symbol. They contain no product design data and do not establish motor
behavior.

| Source                          | SHA-256                                                            | Expected result            |
| ------------------------------- | ------------------------------------------------------------------ | -------------------------- |
| `same-net-motor.kicad_sch`      | `a9d3b9dd3e403bdc1f6fc2403a4a030e57ffadc1cbe85ce585eda6d20e4d8f42` | One REVIEW finding for M1. |
| `distinct-nets-motor.kicad_sch` | `6cfa5b1a856b1a04fabd3c274072b5b03f00f71ce7a218ea5542c344302e172e` | No finding.                |

The native fixture lane exports each source twice with digest-pinned KiCad
10.0.0 and 10.0.5 images. It checks the same-net fault, the separate-net
control, and repeatable normalized netlists. The lane does not run ERC or DRC
and does not prove PCB continuity.

Focused synthetic regression:

```sh
.venv/bin/python -I -m pytest tests/test_two_pin_motors.py \
  -m 'design_lint and component_lint and design_lint_rule(rule_id="component.two_pin_motor_same_net")'
```

Exact-version native regression:

```sh
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_two_pin_component_native_fixture_lane.py \
  -m 'design_lint and component_lint and native_kicad and design_lint_rule(rule_id="component.two_pin_motor_same_net")'
```
