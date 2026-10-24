# Two-pin battery same-net fixture

These tooling-owned schematics exercise `component.two_pin_battery_same_net`
with an exact `Device:Battery` identity and a minimal synthetic two-pin symbol.
They contain no product design data and do not establish battery behavior.

| Source                            | SHA-256                                                            | Expected result             |
| --------------------------------- | ------------------------------------------------------------------ | --------------------------- |
| `same-net-battery.kicad_sch`      | `33d76cb6ac784e7be9b801a938b43a5a98f5d6c2bc55be8bdbb485dfc657673e` | One REVIEW finding for BT1. |
| `distinct-nets-battery.kicad_sch` | `b72525841fa7cbae6cc050db065370ab83990b1728d414f87423c29aa2472711` | No finding.                 |

The native fixture lane exports each source twice with digest-pinned KiCad
10.0.0 and 10.0.5 images. It checks the same-net fault, the separate-net
control, and repeatable normalized netlists. The lane does not run ERC or DRC
and does not prove PCB continuity.

Focused synthetic regression:

```sh
.venv/bin/python -I -m pytest tests/test_two_pin_batteries.py \
  -m 'design_lint and component_lint and design_lint_rule(rule_id="component.two_pin_battery_same_net")'
```

Exact-version native regression:

```sh
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_two_pin_component_native_fixture_lane.py \
  -m 'design_lint and component_lint and native_kicad and design_lint_rule(rule_id="component.two_pin_battery_same_net")'
```
