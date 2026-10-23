# SPI clock/select label mismatch fixtures

These Tooling-owned synthetic schematics exercise the bounded
`bus.spi_clock_select_label_mismatch` review heuristic. They contain no
project or cohort board data.

| Source                              | Purpose                                                                    | SHA-256                                                            |
| ----------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `crossed-labels.kicad_sch`          | `SPI1_SCK` is assigned to `SPI1_CS`; `SPI1_NSS` is assigned to `SPI1_SCK`. | `aeedfe05f1997dfefe547d83a474e1c527a1f482c1e58b7700846cc80404d19f` |
| `matching-labels-control.kicad_sch` | `SPI1_SCK` and `SPI1_NSS` are assigned to matching clock/select labels.    | `0b52bf3893cfcee36727bb82257d650538835c3153fe0f71b62dfac58d6b4c3c` |

The symbols use passive electrical pin types so ERC does not hide the lint
behavior behind output-driver checks. The native lane repeats XML netlist and
ERC exports with the digest-pinned KiCad 10.0.0 and 10.0.5 images. The check
does not establish the device's authoritative pin map, intended topology,
protocol behavior, PCB copper, or off-board wiring.

Run the fast and native cases with:

```sh
.venv/bin/python -I -m pytest tests/test_spi_clock_select_label_mismatch.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.spi_clock_select_label_mismatch")'

KICAD_RUN_NATIVE_SPI_CLOCK_SELECT_LABEL_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_spi_clock_select_label_mismatch_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.spi_clock_select_label_mismatch")'
```
