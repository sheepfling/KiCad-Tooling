# SPI data-label polarity fixtures

These schematics are synthetic tooling fixtures. They contain a two-pin SPI
controller symbol with native MOSI and MISO functions. The fault exchanges the
explicit `SPI_MOSI` and `SPI_MISO` labels; the control keeps them aligned.

| Case    | Source                           | SHA-256                                                            |
| ------- | -------------------------------- | ------------------------------------------------------------------ |
| Control | `correct-spi-lines.kicad_sch`    | `6b29be20a44658188f5df0eebf1757e10ff6d3345f9301f336986acec932a782` |
| Fault   | `mismatched-spi-lines.kicad_sch` | `cc21af60fd62c2c1ee87e1ac4850b21cce610914c308dd734ed9de1f88fa129a` |

The digest-pinned native lane exports both schematics twice using the exact
KiCad 10.0.0 or 10.0.5 image declared by the regression, normalizes the
exported netlists, and verifies the expected review findings. The lane
validates native export and analyzer repeatability; it does not establish
hardware intent or board routing.

Run the focused checks from the tooling checkout:

```sh
.venv/bin/python -I -m pytest tests/test_spi_data_label_polarity.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.spi_data_polarity_label_mismatch")'

KICAD_RUN_NATIVE_SPI_DATA_POLARITY_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_spi_data_polarity_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.spi_data_polarity_label_mismatch")'
```
