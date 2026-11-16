# Synthetic USB multi-stage series-chain fixture

This tooling-owned schematic models a USB 2.0 connector-to-PHY path with two
fitted, passive, two-pin `Device:R` stages on each data line. It contains no
product or proprietary source. The rule uses only the native netlist topology
to request project review; it does not judge resistor values, prove conduction,
or establish PCB connectivity.

| Fixture                                                         | Expected result                                                                   |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `two-stage-fault.kicad_sch`                                     | One `bus.usb_unmapped_series_chain` REVIEW prompt with both exact resistor chains |
| `../usb-data-path-native/external-phy-series-control.kicad_sch` | Quiet control with one resistor stage per data line                               |

Fixture SHA-256:

| Fixture                     | SHA-256                                                            |
| --------------------------- | ------------------------------------------------------------------ |
| `two-stage-fault.kicad_sch` | `d41707fc9e2392d6933f03ea66949a30082128cf508fabaab0a3b4aaf916c9a8` |

The native acceptance lane re-exports each schematic twice with KiCad 10.0.0
from its digest-pinned Docker image, parses the native XML into the regular
`NetlistContract`, and evaluates the same rule used for synthetic tests:

```sh
KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES=1 \
.venv/bin/python -I -m pytest -q tests/test_usb_unmapped_series_chain_native.py \
  -m 'design_lint and interface_lint and native_kicad'
```
