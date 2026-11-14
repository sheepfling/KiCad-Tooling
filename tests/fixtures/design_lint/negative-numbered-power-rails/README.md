# Numbered negative supply rail fixtures

These tooling-owned schematics are derived from the synthetic channel-power
fixture. Only the project title and the pin 3 net labels changed. They contain
no product, customer, or cohort source.

| Case    | J1.3    | J2.3      | Expected `net.numbered_power_rails` result                  |
| ------- | ------- | --------- | ----------------------------------------------------------- |
| Fault   | `-5V_1` | `-5.0V-2` | One REVIEW candidate with both exact net-to-pin assignments |
| Control | `-5V_1` | `-5V_1`   | No numbered-rail candidate                                  |

The VDD function and native connector metadata are otherwise unchanged. A
similar negative-voltage label is a review clue only; the rule does not require
the nets to be joined, determine the actual voltage, or inspect PCB continuity.

## Source hashes

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `efd12982e8dfb4ee93cbb6888dae821ba0a26a9a3bfa3411a3f8c1b5c93bf16e` |
| `control.kicad_sch` | `73b371ae8c83e505c7e58ae946a4cf2b448e20c4d022b1c4927ec734c481d103` |

## Exact native export lane

The focused test exports each schematic twice with digest-pinned KiCad 10.0.0
and 10.0.5 Docker images, compares normalized netlist hashes, and runs the
typed lint against those exports. Generated receipts remain under ignored
`build/` directories.

```sh
KICAD_TEMPLATE_ROOT=/absolute/path/to/KiCad-Test \
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q \
  tests/test_design_lint_numbered_power_rails.py \
  tests/test_design_lint_determinism_numbered_power_rails.py \
  tests/test_numbered_negative_power_rail_native_fixture_lane.py \
  -m 'design_lint and power_lint and design_lint_rule(rule_id="net.numbered_power_rails")'
```
