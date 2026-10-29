# Ethernet data one-sided-open fixtures

These tooling-owned synthetic schematics exercise the opt-in
`bus.ethernet_data_unconnected_pin` review heuristic. They contain no product
or proprietary project source.

| Case                | Native assignments                                                           | Expected target finding                                           |
| ------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `control.kicad_sch` | U1.1 TDP, U1.2 TDN, U1.3 RDP, and U1.4 RDN each have a distinct named net    | None                                                              |
| `fault.kicad_sch`   | U1.1 TDP is explicitly no-connect; the other three data pins remain assigned | One candidate localized to open U1.1 TDP beside assigned U1.2 TDN |

The rule is off by default because an unused lane can be intentional. The
fault fixture tests how the native export represents an explicit open pin; it
does not establish an electrical requirement.

SHA-256 source hashes:

| File                | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `e09b9f446dc871b84c0a88580bed818f4911853db6eba30250fcf6a9678dc87a` |
| `fault.kicad_sch`   | `ab1396840c5b2fff690a759a8303ba12024a66261374595cf3bfcc420884f0f1` |

The exact-version lane exports both sources twice with digest-pinned KiCad
10.0.0 and 10.0.5 images, then checks normalized netlist repeatability and the
target rule result:

```sh
KICAD_RUN_NATIVE_ETHERNET_DATA_UNCONNECTED_FIXTURES=1 \
  .venv/bin/python -I -m pytest tests/test_ethernet_data_unconnected_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.ethernet_data_unconnected_pin")'
```
