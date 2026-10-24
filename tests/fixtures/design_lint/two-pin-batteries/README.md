# Two-pin battery same-net fixture

These tooling-owned schematics exercise `component.two_pin_battery_same_net`
with exact stock and project-mapped custom battery identities and minimal
synthetic two-pin symbols. They contain no product design data and do not
establish battery behavior.

| Source                                   | SHA-256                                                            | Expected result                                        |
| ---------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------ |
| `same-net-battery.kicad_sch`             | `33d76cb6ac784e7be9b801a938b43a5a98f5d6c2bc55be8bdbb485dfc657673e` | One REVIEW finding for BT1.                            |
| `distinct-nets-battery.kicad_sch`        | `b72525841fa7cbae6cc050db065370ab83990b1728d414f87423c29aa2472711` | No finding.                                            |
| `mapped-same-net-battery.kicad_sch`      | `9b3c3aa34bc967ef32e217e46f53d4bed1e910d810325b1eaa8c5f912e710edb` | One REVIEW finding for BT1 through the exact role map. |
| `mapped-distinct-nets-battery.kicad_sch` | `2cfeb1ac0d450512915068b5c6636718ae23d2931a3867d99e66b9a0ad1dc191` | No finding with the matching role map.                 |

The custom fixtures bind PART_ID, symbol, footprint, and the complete native
pin number/function/electrical-type inventory. The map uses only synthetic
identities and does not infer behavior from the symbol name.

The native fixture lane exports each source twice with digest-pinned KiCad
10.0.0 and 10.0.5 images. It checks the stock and mapped same-net faults,
their separate-net controls, and repeatable normalized netlists. The lane
does not run ERC or DRC and does not prove PCB continuity.

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
