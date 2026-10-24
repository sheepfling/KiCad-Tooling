# Synthetic SPI signal assigned to a named rail

These Tooling-authored schematics test
`bus.spi_signal_on_named_rail`. They are minimal review fixtures and contain no
project board data.

| Source              | Purpose                                                       | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | The fitted IC's `SPI1_SCK` pin is directly assigned to `GND`. | `ea7aa06bf78c24996bdfa8754c88822cb0a6ed8b86b0c6010ab9b79f6705aebf` |
| `control.kicad_sch` | `SPI1_SCK` and `SPI1_NSS` use their separate signal nets.     | `8c18aae7ec349d9e971928e85dfc4843397aad1a3f7623100d25cc1b7d4e5221` |

The native fixture lane exports each source twice with digest-pinned KiCad 10.0.0
and 10.0.5 images. It confirms stable netlist and ERC evidence, zero ERC errors,
one REVIEW candidate on the fault, and no named-rail candidate on the control.
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
