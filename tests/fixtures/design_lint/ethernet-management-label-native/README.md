# Ethernet management-label mismatch fixtures

These source-hashed schematic inputs are synthetic tooling fixtures. They do
not contain project or customer design data. The MDC/MDIO management signal
names follow the public [TI DP83826E/DP83826I datasheet](https://www.ti.com/lit/gpn/DP83826I),
which identifies MDC as the management clock and MDIO as the management input/output data pin.

- `control.kicad_sch` assigns native MDC and MDIO pins to `ETH_MDC` and
  `ETH_MDIO` respectively.
- `fault.kicad_sch` crosses those labels while retaining one unique net per pin.

Reviewed SHA-256 values:

- `control.kicad_sch`: `3ddd8d2919eade8a6bb8f7a8c059dafbe9b348aacbb5a6bb8398b0c62944d31b`
- `fault.kicad_sch`: `f63b39e17d68c36202e323534f2ea58b63247a2e55b0188bc048056d26cf1495`

The exact-version acceptance lane exports both inputs twice using digest-pinned
KiCad 10.0.0 and 10.0.5 images. It checks repeatable normalized netlists,
complete pin/function/net evidence, a quiet control, and two exact findings on
the crossed-label fault. It runs with networking disabled and mounts only
these synthetic schematics and an output directory.

```sh
KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_LABEL_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q \
  tests/test_ethernet_management_label_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.ethernet_management_label_mismatch")'
```
