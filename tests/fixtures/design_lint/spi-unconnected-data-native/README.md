# SPI open data-pin fault and control

These source-hashed schematics are synthetic tooling fixtures, derived from
the tooling repository's existing synthetic two-pin SPI schematic. The fault
adds a native no-connect marker to U1.1 (MOSI) while U1.2 (MISO) remains
assigned. The control assigns both data pins. No project or cohort board
source is included.

| Case    | Source                | SHA-256                                                            |
| ------- | --------------------- | ------------------------------------------------------------------ |
| Control | `control.kicad_sch`   | `af3490ef9bd15a32ec307a50c807a56611ca3f2e6e597bc66368b4fdadc97a2a` |
| Fault   | `open-mosi.kicad_sch` | `d18786cbb35cf58f723b452b12b61abe5b3f347ebc1a540e3b9655097e98f13d` |

The rule defaults to `off`. The native gate checks that KiCad exports only
U1.1 as newly unassigned, the opt-in review reports `U1.1: MOSI`, the connected
control is quiet, and repeated normalized netlists match on digest-pinned KiCad
10.0.0 and 10.0.5. This validates the parser and evidence adapter; it does not
establish whether a physical device should use both directions or prove PCB
copper continuity.

Run the focused checks from the tooling checkout:

```sh
.venv/bin/python -I -m pytest tests/test_spi_unconnected_data_pins.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.spi_unconnected_data_pin")'

KICAD_RUN_NATIVE_SPI_UNCONNECTED_DATA_FIXTURES=1 \
  .venv/bin/python -I -m pytest tests/test_spi_unconnected_data_pins_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.spi_unconnected_data_pin")'
```
