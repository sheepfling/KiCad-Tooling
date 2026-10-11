# CAN peer-reference native fixtures

These standalone schematics are synthetic tooling fixtures. They contain no
project-board source or project-owned electrical expectations.

| Fixture                       | Purpose                                                                                        | SHA-256                                                            |
| ----------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `reference-control.kicad_sch` | Three fitted CAN endpoints share exact CANH/CANL nets and a common explicit `GND_A` reference. | `ece18cddcf6fb122bcbcd46a7b4792426735146a6a923b62b68642ef0903a96a` |
| `reference-fault.kicad_sch`   | Same line pair and supplies, with U1/U2 on `GND_A` and a distinct-symbol U3 on `GND_B`.        | `4e636cab9d214f97e68640f1d200df6067d49e83d571ce3e8e117527517103a8` |

U1 and U2 share one exact symbol identity and the same pin assignments, so
component-peer checks do not cover the split. U3 has a separate exact symbol
identity. The CAN review rule should report the split line-pair group once; it
does not assert that the return nets must be joined. The fixtures expose all
four pins on every endpoint in the symbol definition and connect each reference
and supply pin in the drawing.

The hosted lane exports each fixture twice with digest-pinned KiCad 10.0.0 and
10.0.5 images. It compares normalized netlists and ERC reports, requires zero
ERC errors, checks each CAN/reference/supply pin assignment, and verifies the
expected review candidate and common-reference control.

Run the native lane from the tooling checkout with the public template checkout
configured as `KICAD_TEMPLATE_ROOT`:

```sh
KICAD_RUN_NATIVE_CAN_PEER_REFERENCE_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_can_native_fixture_lanes.py::test_native_can_peer_reference_fault_and_control
```
