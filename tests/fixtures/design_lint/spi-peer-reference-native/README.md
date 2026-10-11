# Synthetic SPI peer-reference fixtures

These standalone KiCad schematics are synthetic regression inputs. They contain
no product or contributor project data and are marked not for manufacture.

- `control.kicad_sch` connects a controller and peripheral through native SCK
  and MOSI nets, assigns both VDD pins to `+3V3`, and uses one reference net.
- `fault.kicad_sch` preserves that topology and supply rail while assigning
  the two explicit GND pins to separate nets.

The exact-native regression exports each source twice through the digest-pinned
KiCad 10.0.0 and 10.0.5 images. It checks normalized-netlist repeatability,
equal voltage-named supplies, and common-reference control versus
split-reference review. The local synthetic selector is
`tests/test_spi_peer_reference_review.py`; the hosted exact-native selector is
`tests/test_spi_peer_reference_native_fixture_lane.py`.

The fixtures validate the schematic-netlist predicate only. They do not
establish that separate references are wrong, require common grounding, prove
PCB continuity, or validate SPI timing or electrical performance.
