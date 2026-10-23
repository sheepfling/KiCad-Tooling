# USB connector-to-PHY data-pair crossing fixtures

These tooling-owned schematics test whether a complete USB 2.0 data pair keeps
the same D+/D− roles between a connector and PHY when the net names are neutral.
They are synthetic regression fixtures and contain no product or proprietary
source.

| Case                | Native assignments                                                               | Expected lint result                                         |
| ------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `control.kicad_sch` | Connector D+ to PHY D+ on `USB_ROUTE_A`; connector D− to PHY D− on `USB_ROUTE_B` | No `bus.usb_peer_data_pair_crossed` candidate                |
| `fault.kicad_sch`   | Connector D+ to PHY D− on `USB_ROUTE_B`; connector D− to PHY D+ on `USB_ROUTE_A` | One REVIEW candidate identifying J1/U1 and both crossed nets |

Both fixtures retain a common reference net and complete native pin inventories.
The fault differs from the control only in the connector-side data-net
assignments. SHA-256 hashes:

| File                | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `e0cf5d7a0f585b025ad4dc28861a19d37e1af78b79da518ff6032fd32e97c239` |
| `fault.kicad_sch`   | `29b47ef57440ff01c634efa31192fbe89b2af06bfc8ae95c563a28b847a30bdb` |

The native fixture lane exports both sources twice with the digest-pinned KiCad
10.0.0 and 10.0.5 images, parses each export through the same normalized
netlist service, and checks repeatability. The neutral route names ensure the
existing net-label polarity lint does not supply the finding. The check is
limited to exact direct USB 2.0 paths with bounded D-designated protection
branches; it does not verify PCB routing, device behavior, or the authoritative
pinout.

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_USB_DATA_POLARITY_FIXTURES=1 \
.venv/bin/python -I -m pytest -q tests/test_usb_data_polarity_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.usb_peer_data_pair_crossed")'
```
