# Synthetic SPI signal assigned to a named rail

These Tooling-authored schematics test
`bus.spi_signal_on_named_rail`. They are minimal review fixtures and contain no
project board data.

| Source              | Purpose                                                                                                     | SHA-256                                                            |
| ------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | The fitted IC's `SPI1_SCK` and connector's `SPI2_SCK` pins are assigned to `GND`.                           | `ff78ffd2e8bec8c68a6a72cec9d8a2bfdd46e514646f05cf31405d29d3c6643b` |
| `control.kicad_sch` | The IC and connector clock pins use separate signal nets; the connector's `GND_B` return remains unchanged. | `30d060168425387083f95022aca995be3e2cca22ac512dc49f0a343b62572242` |

The native fixture lane exports each source twice with digest-pinned KiCad 10.0.0
and 10.0.5 images. It confirms stable netlist and ERC evidence, zero ERC errors,
an IC and a connector REVIEW candidate on the fault, and no named-rail candidate
on the control.
The lint is a prompt to inspect the function and net-name combination. It does
not decide whether the rail strap is intentional or prove potential, PCB copper,
or physical continuity.

Run the focused regressions with:

```sh
.venv/bin/python -I -m pytest tests/test_spi_signal_named_rail.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.spi_signal_on_named_rail")'

KICAD_RUN_NATIVE_SPI_SIGNAL_NAMED_RAIL_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_spi_signal_named_rail_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.spi_signal_on_named_rail")'
```
