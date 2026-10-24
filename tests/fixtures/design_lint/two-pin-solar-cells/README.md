# Two-pin solar-cell same-net fixtures

These tooling-owned schematics exercise
`component.two_pin_solar_cell_same_net` with an exact `Device:Solar_Cell`
identity and a minimal synthetic two-pin symbol definition. The embedded
geometry is only a native-netlist test fixture; it is not a source copy of a
KiCad library symbol or a product design.

| Source                               | SHA-256                                                            | Expected result             |
| ------------------------------------ | ------------------------------------------------------------------ | --------------------------- |
| `same-net-solar-cell.kicad_sch`      | `9bfc6cbd16fe471fd9edc869c5ccab715f97a7067fdf15680e5123b765eb57e6` | One REVIEW finding for BT1. |
| `distinct-nets-solar-cell.kicad_sch` | `df1aac38d4e3f352fe4d1358e0a786ce144b921552eedae3e2d380aa165bdb9d` | No finding.                 |

The native fixture lane exports each source twice using digest-pinned KiCad
10.0.0 and 10.0.5 images. It checks the same-net fault, the separate-net
control, and repeatable normalized netlists. It does not run ERC or DRC and
does not prove solar-cell behavior or PCB continuity.

Focused synthetic regression:

```sh
.venv/bin/python -I -m pytest tests/test_two_pin_solar_cells.py \
  -m 'design_lint and component_lint and design_lint_rule(rule_id="component.two_pin_solar_cell_same_net")'
```

Exact-version native regression:

```sh
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_two_pin_component_native_fixture_lane.py \
  -m 'design_lint and component_lint and native_kicad and design_lint_rule(rule_id="component.two_pin_solar_cell_same_net")'
```
