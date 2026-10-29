# RS-485 A/B line-label mismatch fixtures

These synthetic schematics exercise `bus.rs485_line_label_mismatch`. Both
sources use an explicit synthetic RS-485 transceiver identity and passive A/B
pins so native ERC does not decide the line-name review.

| Case                | Source SHA-256                                                     |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `088e4f94449678f4ccb01569d69220dc3c225e533848a8e91a05586d6eac1400` |
| `fault.kicad_sch`   | `fee16129e0b52695475b47f2da3d3e83dc559ec405e2c8b4ca9456069e7bc9d6` |

The fault reverses the explicit RS485_A/RS485_B labels on the A/B pin
functions. The control assigns each function to its matching label. The
heuristic is only a REVIEW clue because part pinouts and A/B conventions can
vary; it does not establish correct cable polarity, board routing, or physical
continuity.

Exact-version native acceptance repeats netlist and ERC exports with
digest-pinned KiCad 10.0.0 and 10.0.5 images.

```sh
.venv/bin/python -I -m pytest tests/test_rs485_line_label_mismatch.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.rs485_line_label_mismatch")'

KICAD_RUN_NATIVE_RS485_LINE_LABEL_MISMATCH_FIXTURES=1 \
  .venv/bin/python -I -m pytest tests/test_rs485_line_label_mismatch_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.rs485_line_label_mismatch")'
```
