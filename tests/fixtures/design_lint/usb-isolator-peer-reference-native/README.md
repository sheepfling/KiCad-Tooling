# Synthetic USB isolator reference boundary

This tooling-authored schematic is a compact regression fixture. It contains no
external project source. U1 is a synthetic two-port USB isolator with separate
host-side and device-side reference pins.

Select the typed boundary regression with:

```sh
python -I -m pytest tests/test_usb_isolator_peer_reference.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.usb_peer_reference_review")'
```

| Port   | Connector data pins | U1 data pins | Reference domain              |
| ------ | ------------------- | ------------ | ----------------------------- |
| Host   | J1.1/J1.2           | U1.1/U1.2    | J1.4 and U1.3 on `HOST_GND`   |
| Device | J2.1/J2.2           | U1.4/U1.5    | J2.4 and U1.6 on `DEVICE_GND` |

The native fixture lane maps both direct data paths to U1 by exact pin and net.
The USB peer-reference heuristic must remain quiet because U1 has reference pins
in two domains, which is outside its supported endpoint predicate. Its coverage
must report `INCOMPLETE`: two supported connector groups, two incomplete U1
port groups, zero supported PHY groups, and zero supported data paths. This is
not a supported non-finding and does not imply the return domains should be
joined.

The source SHA-256 is
`d1a785a983b18315b402d003990056c2f3e5aab40e8bb937e3f44ffc901946d9`.
The exact digest-pinned KiCad 10.0.0 and 10.0.5 acceptance runs through
`tests/test_usb_data_path_native_fixture_lane.py` after the tagged fixture lane
is pushed. A local no-native run cannot establish that KiCad exported this
schematic as expected.
