# USB D+/D- resistive bridge review fixtures

These synthetic schematics place one bidirectional USB-like PHY on distinct
`USB_DP` and `USB_DM` nets. The fault case adds a fitted 90 Ω `Device:R`
directly between those nets. The control has separate, unbridged data nets.
This models a potential connection that native net-based checks alone cannot
classify as wrong; the heuristic emits a configurable REVIEW because a
differential termination or other intentional shunt may be valid.

Native exports confirm the pin functions, exact net assignments, no ERC errors,
repeatability, and the expected lint result with digest-pinned KiCad 10.0.0 and
10.0.5. The fixture contains no product design or external project source.

| Case | Source | SHA-256 |
| --- | --- | --- |
| Fault | `fault.kicad_sch` | `511276b9f7e82f01c446e9ee05952089084900101de33fe9d843eed97a320f6e` |
| Control | `control.kicad_sch` | `3cf34e863b751d9ec713775ca51732bda4c60829e47d63e1c4b148b709f3bf3d` |

Run focused checks from the tooling checkout:

```sh
.venv/bin/python -I -m pytest tests/test_usb_data_pair_resistive_bridge.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.usb_dp_dm_resistive_bridge")'

KICAD_RUN_NATIVE_USB_DP_DM_RESISTIVE_BRIDGE_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_usb_data_pair_resistive_bridge_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.usb_dp_dm_resistive_bridge")'
```
