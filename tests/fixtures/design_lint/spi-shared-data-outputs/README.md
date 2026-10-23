# Synthetic SPI shared-data fixtures

These schematics are tooling-owned fixtures for
`bus.spi_data_outputs_share_net`. They contain no project or cohort design
source.

| Source              | SHA-256                                                            | Expected lint result                                             |
| ------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------- |
| `fault.kicad_sch`   | `b22837132aeff633a2a91c023a6f49c8469326593bee4942e37f2568a6d5bfb6` | Review U2.1 and U3.1 sharing `SPI_MISO`                          |
| `control.kicad_sch` | `f8265c27a9c20a40e44232374c3650a0f17a23c066db3fe9d6dd6b5911b3ae85` | No finding: only one fitted output pin is assigned to `SPI_MISO` |

The native lane repeats netlist and ERC exports with digest-pinned KiCad
10.0.0 and 10.0.5 images. Both sources must have no ERC errors, normalized
netlist evidence must repeat exactly, the fault must yield one candidate, and
the control must remain quiet. Multiple output pins sharing a data net can be
intentional on a tri-state bus, so the rule defaults off and asks for review.

Focused commands:

```sh
.venv/bin/python -I -m pytest tests/test_spi_shared_data_outputs.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.spi_data_outputs_share_net")'

KICAD_RUN_NATIVE_SPI_SHARED_DATA_OUTPUT_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_spi_shared_data_outputs_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.spi_data_outputs_share_net")'
```
