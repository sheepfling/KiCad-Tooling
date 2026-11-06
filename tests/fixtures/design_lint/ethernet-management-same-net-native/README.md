# Ethernet management MDC/MDIO same-net fixtures

These source-hashed schematics are synthetic tooling fixtures. They do not
contain project or customer design data. The MDC and MDIO native functions
follow the public [TI DP83826E/DP83826I datasheet](https://www.ti.com/lit/gpn/DP83826I),
which identifies the two management pins separately.

- `control.kicad_sch` assigns MDC and MDIO to distinct neutral nets.
- `fault.kicad_sch` assigns both exact native pins to `MII_MANAGEMENT`.

Reviewed SHA-256 values:

- `control.kicad_sch`: `3ddd8d2919eade8a6bb8f7a8c059dafbe9b348aacbb5a6bb8398b0c62944d31b`
- `fault.kicad_sch`: `7cc82eec2c6ef277e34d7b506eb430518c28d3ef9126db01b01953ba3c4d4568`

The native lane exports both schematics twice with digest-pinned KiCad 10.0.0
and 10.0.5 images. It compares repeatable normalized netlists, exact pin
functions and assignments, a quiet distinct-net control, and one localized
same-net REVIEW finding. Networking is disabled in the container, which mounts
only these synthetic schematics and an output directory.

```sh
KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_SAME_NET_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q \
  tests/test_ethernet_management_same_net_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.ethernet_management_same_net")'
```
