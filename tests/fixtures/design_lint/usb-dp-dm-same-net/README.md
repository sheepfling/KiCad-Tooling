# USB 2.0 D+/D- same-net fixtures

These tooling-owned schematics contain a synthetic USB PHY with explicit
bidirectional `DP` and `DM` pin functions, bounded aliases for USB D+ and D-.
The fault assigns both pins
to `USB_SHARED`; the control assigns pin 1 to `USB_DP` and pin 2 to `USB_DM`.
The pair uses bidirectional electrical types so the fault has no ERC conflict;
this demonstrates a review gap that a separate source-net heuristic can cover.

Exact-version exports check the native pin functions, net assignments,
repeatability, and ERC result on KiCad 10.0.0 and 10.0.5. The rule remains a
configurable review prompt because function labels alone do not prove USB use
or the intended topology.

| Case    | Source              | SHA-256                                                            |
| ------- | ------------------- | ------------------------------------------------------------------ |
| Fault   | `fault.kicad_sch`   | `7182133d074e5f28fa7a80b36962ed11b4e659e85e107db9dbc5c708c5110ebe` |
| Control | `control.kicad_sch` | `ac9410b7cade422a635847bae9e1e4a7a57333a7a259756d4aad62afa8d8069e` |

Run the focused tests from the tooling checkout:

```sh
.venv/bin/python -I -m pytest tests/test_usb_data_same_net.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.usb_dp_dm_same_net")'

KICAD_RUN_NATIVE_USB_DP_DM_SAME_NET_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_usb_data_same_net_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.usb_dp_dm_same_net")'
```

All inputs are synthetic and contain no external project source.
