# Ethernet data-label mismatch fixtures

These source-hashed schematic inputs are synthetic tooling fixtures. They do
not contain project or customer design data. The pair pin-function aliases
follow Ethernet PHY naming used in public component documentation, including
[TI DP83826](https://www.ti.com/lit/ds/symlink/dp83826e.pdf) and
[Microchip VSC8211](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/VMDS-10105.pdf).

- `control.kicad_sch` maps TDP/TDN to ETH_TX_P/ETH_TX_N and RDP/RDN to
  ETH_RX_P/ETH_RX_N.
- `fault.kicad_sch` swaps the TX/RX pair labels while retaining complete,
  separately named pairs.

Reviewed SHA-256 values:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `9fae1afdb0395354f6e61eae17623f5d940b2f90bf82d452ff8339bfed1e421e` |
| `fault.kicad_sch`   | `8b42bc11362cedc71519b7ffb2477da399c52374efcf44bcb69d35149f9a1b92` |

The exact-version acceptance lane exports each input twice using digest-pinned
KiCad 10.0.0 and 10.0.5 images. It checks repeatable normalized netlists,
complete pin/function/net evidence, no finding on the control, and four exact
findings on the crossed-label fault. It runs with networking disabled and
mounts only these synthetic schematics and an output directory.

```sh
KICAD_RUN_NATIVE_ETHERNET_DATA_LABEL_FIXTURES=1 .venv/bin/python -I -m pytest -q \
  tests/test_ethernet_data_label_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.ethernet_data_label_mismatch")'
```
