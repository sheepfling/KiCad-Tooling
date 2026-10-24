# Two-pin buzzer same-net fixture

These tooling-owned schematics exercise `component.two_pin_buzzer_same_net`
using the exact `Device:Buzzer` library identity and a minimal synthetic
two-pin symbol. They do not contain product design data or establish a buzzer
part's electrical behavior.

| Source | SHA-256 | Expected result |
| --- | --- | --- |
| `same-net-buzzer.kicad_sch` | `6213cd36ed3321bc837d541a82617467524bd2b2454d95be034e2f9bd720f51f` | One REVIEW finding for BZ1. |
| `distinct-nets-buzzer.kicad_sch` | `120688dc3c6600bb729aecf7ca8ef0c43368bacc50d73c4b708a6286c324ef62` | No finding. |

The native fixture lane exports both sources twice with the exact digest-pinned
KiCad 10.0.0 and 10.0.5 images. It checks component identity, the same-net
fault, the separate-net control, and repeatable normalized netlists. This lane
does not run ERC or DRC and does not prove PCB continuity.

Focused synthetic regression:

```sh
.venv/bin/python -I -m pytest tests/test_two_pin_buzzers.py \
  -m 'design_lint and component_lint and design_lint_rule(rule_id="component.two_pin_buzzer_same_net")'
```

Exact-version native regression:

```sh
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_two_pin_component_native_fixture_lane.py \
  -m 'design_lint and component_lint and native_kicad and design_lint_rule(rule_id="component.two_pin_buzzer_same_net")'
```
