# USB-C CC1/CC2 same-net native fixtures

These minimal synthetic schematics exercise both connector-side
`bus.usb_c_cc_same_net` and controller-side
`bus.usb_c_cc_controller_same_net` using KiCad native netlist and ERC exports.
They contain no project or customer design data.

| Source              | SHA-256                                                            | Expected result                                           |
| ------------------- | ------------------------------------------------------------------ | --------------------------------------------------------- |
| `fault.kicad_sch`   | `621079d2d0e3fc5d782a3c6906545beca838857d4fcb3b0c2d500527b72d7c3c` | J1 and U1 CC1/CC2 share `CC_SHARED`; review both targets. |
| `control.kicad_sch` | `1dd9812937047037d7f66d40eb7c9249027a61ccedb7edf140702476b4713d2c` | J1/U1 CC1 and CC2 use separate nets; no finding.          |

The fixtures are checked with repeat native netlist and ERC exports on the
digest-pinned KiCad 10.0.0 and 10.0.5 images. Both cases must have no ERC
errors and identical normalized exports on repeat.

Run the synthetic rule regressions with:

```sh
.venv/bin/python -I -m pytest tests/test_usb_c_cc_same_net.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.usb_c_cc_same_net")'
```

The native lane is selected with
`KICAD_RUN_NATIVE_USB_C_CC_SAME_NET_FIXTURES=1` and
`KICAD_RUN_NATIVE_USB_C_CC_CONTROLLER_SAME_NET_FIXTURES=1`.
