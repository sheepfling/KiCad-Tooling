# Active regulator-support pin-to-net fixtures

These tooling-owned synthetic schematics test
`power.regulator_support_pin_net_mismatch`. The project map supplies the exact
active-component identities and every expected native pin assignment.

| Fixture                 | Change                                                       | Expected result    |
| ----------------------- | ------------------------------------------------------------ | ------------------ |
| `control.kicad_sch`     | All mapped active support pins use their authored exact nets | No pin-net finding |
| `wrong-net.kicad_sch`   | U2.1 is assigned to a different local net                    | REVIEW for U2      |
| `unconnected.kicad_sch` | U3.3 is explicitly left unconnected                          | REVIEW for U3      |

Run the synthetic cases with
`python -I -m pytest tests/test_regulator_support_pin_net_map.py -m 'design_lint and power_lint'`.
The exact KiCad 10.0.0 and 10.0.5 lane uses
`KICAD_RUN_NATIVE_REGULATOR_SUPPORT_PIN_NET_FIXTURES=1` and
`tests/test_regulator_support_pin_net_native_fixture.py`.

The fixtures validate comparison against project-authored expectations. They
do not establish that those expectations match a datasheet or that schematic
net assignments form a physical PCB connection.
