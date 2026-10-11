# Synthetic I2C peer-reference fixtures

These generated-style KiCad schematics are standalone, synthetic regression
inputs. They contain no product, customer, or contributor project data and are
marked not for manufacture.

- `control.kicad_sch`: two distinct IC symbols on the same SDA/SCL pair with a
  common assigned reference net.
- `fault.kicad_sch`: the same topology with the two reference pins assigned to
  separate nets.

The exact-native regression exports both sources twice through the project's
digest-pinned KiCad 10.0.0 and 10.0.5 images, checks the normalized netlists for
repeatability, and verifies common-reference control versus split-reference
review. The locally runnable synthetic selector is
`tests/test_i2c_peer_reference_review.py`; the hosted native selector is
`tests/test_i2c_peer_reference_native_fixture_lane.py`.

These fixtures validate exported schematic topology and deterministic lint
classification. They do not establish that separate references are wrong or
prove PCB connectivity, grounding approval, or physical continuity.
