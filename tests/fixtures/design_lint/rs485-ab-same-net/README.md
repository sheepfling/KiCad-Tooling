# RS-485 A/B same-net fixtures

These Tooling-owned synthetic schematics exercise
`bus.rs485_ab_same_net`. The fault assigns one explicitly identified synthetic
RS-485 transceiver's A and B pins to the same schematic net. The control keeps
the two lines separate. Both pins use passive native electrical types so the
review heuristic remains independently observable from ERC output-driver
diagnostics.

- `fault.kicad_sch`: A and B share `AB_SHARED`. SHA-256:
  `12df9c40538c819cbd6369cb88f264d4497dff69051e20d3d2c17314bcb13f61`.
- `control.kicad_sch`: A is on `RS485_A`; B is on `RS485_B`. SHA-256:
  `088e4f94449678f4ccb01569d69220dc3c225e533848a8e91a05586d6eac1400`.

The review requires exact A/B functions, fitted U/IC identity explicitly
containing RS-485, one pin for each role, membership in the native component
pin inventory, and one net assignment per pin. Generic A/B functions,
connectors, DNP parts, duplicate roles, open or multiply assigned pins, and
incomplete inventory are outside the rule. Two output pins are left to ERC.
The finding is configurable and defaults to review; an intentionally shared
assignment can be blocked, disabled, or ignored by exact finding fingerprint.

The native lane repeats netlist and ERC exports using digest-pinned KiCad
10.0.0 and 10.0.5 images. The check does not establish the exact part pinout,
the required bus topology, PCB copper connectivity, or physical continuity.

Run the focused cases with:

```sh
.venv/bin/python -I -m pytest tests/test_rs485_ab_same_net.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.rs485_ab_same_net")'

KICAD_RUN_NATIVE_RS485_AB_SAME_NET_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_rs485_ab_same_net_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.rs485_ab_same_net")'
```
