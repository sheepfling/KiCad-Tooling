# Synthetic SPI shared chip-select fixtures

These schematics are tooling-owned fixtures for
`bus.spi_chip_select_inputs_share_net`. They contain no project or cohort
design source.

| Source              | SHA-256                                                            | Expected lint result                                |
| ------------------- | ------------------------------------------------------------------ | --------------------------------------------------- |
| `fault.kicad_sch`   | `07cb6cd5633436b444c92fadb4b512284c4fad8d54ab2127a0de7f81e5011cc1` | Review U2.1 and U3.1 sharing `SPI_CS0`              |
| `control.kicad_sch` | `5fedc3b7347b17ec78b4c775773cef64b2e1df7b4a59d21fc22343759c5c8b2e` | No finding: the two inputs use separate select nets |

The native lane repeats both netlist and ERC exports with digest-pinned KiCad
10.0.0 and 10.0.5 images. Both sources must have no ERC errors, normalized
netlist evidence must repeat exactly, the fault must yield one candidate, and
the separate-select control must remain quiet.

Focused commands:

```sh
.venv/bin/python -I -m pytest tests/test_spi_shared_chip_select.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.spi_chip_select_inputs_share_net")'

KICAD_RUN_NATIVE_SPI_SHARED_CHIP_SELECT_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_spi_shared_chip_select_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.spi_chip_select_inputs_share_net")'
```
