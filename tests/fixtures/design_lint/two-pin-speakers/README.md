# Two-pin speaker same-net fixture

These tooling-owned schematics exercise
`component.two_pin_speaker_same_net` with the exact `Device:Speaker` library
identity and a minimal synthetic two-pin symbol. They contain no product
design data and do not establish a speaker's electrical behavior.

| Source                            | SHA-256                                                            | Expected result             |
| --------------------------------- | ------------------------------------------------------------------ | --------------------------- |
| `same-net-speaker.kicad_sch`      | `8d82fc391cf146a8f9c92c71ae37f6757422ca8599b0e13a69a0de378ecc7a1d` | One REVIEW finding for LS1. |
| `distinct-nets-speaker.kicad_sch` | `e12366fd7846a7585e4bf0cba9dc3203c1669b348ee76581285edd79c3d54287` | No finding.                 |

The native fixture lane exports each source twice with digest-pinned KiCad
10.0.0 and 10.0.5 images. It checks symbol identity, the same-net fault, the
separate-net control, and repeatable normalized netlists. The lane does not run
ERC or DRC and does not prove PCB continuity.

Focused synthetic regression:

```sh
.venv/bin/python -I -m pytest tests/test_two_pin_speakers.py \
  -m 'design_lint and component_lint and design_lint_rule(rule_id="component.two_pin_speaker_same_net")'
```

Exact-version native regression:

```sh
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_two_pin_component_native_fixture_lane.py \
  -m 'design_lint and component_lint and native_kicad and design_lint_rule(rule_id="component.two_pin_speaker_same_net")'
```
