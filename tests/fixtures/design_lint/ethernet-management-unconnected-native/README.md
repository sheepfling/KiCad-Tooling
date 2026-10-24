# Ethernet management one-sided-open fixtures

These tooling-owned synthetic schematics exercise the opt-in
`bus.ethernet_management_unconnected_pin` review heuristic. They contain no
product or proprietary project source.

| Case                | Native MDC/MDIO assignments                            | Expected target finding                  |
| ------------------- | ------------------------------------------------------ | ---------------------------------------- |
| `control.kicad_sch` | U1.5 MDC → `ETH_MDC`; U1.6 MDIO → `ETH_MDIO`           | None                                     |
| `fault.kicad_sch`   | U1.5 MDC explicitly no-connect; U1.6 MDIO → `ETH_MDIO` | One candidate localized to open U1.5 MDC |

The candidate is off by default because an unused management interface can be
intentional. The fault fixture proves the native adapter recognizes an explicit
no-connect as open; it does not make that condition an electrical requirement.
The unit suite separately checks both-open, DNP, duplicate-role, incomplete
inventory, ambiguous-assignment, policy, ignore, ordering, and repair controls.

SHA-256 source hashes:

| File                | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `c3c259a0ce8d0b4be736be63bb106096657b4c596985557460351a88a0e326d6` |
| `fault.kicad_sch`   | `d2324d82038d896ed81727d7934c80e0549e7605c369adabd5c5f2ca81604988` |

The native fixture test exports both sources twice with digest-pinned KiCad
10.0.0 and 10.0.5 images, parses them through the normal netlist reader, and
checks normalized export repeatability and the target rule result. Run it with:

```sh
KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_UNCONNECTED_FIXTURES=1 \
  .venv/bin/python -I -m pytest tests/test_ethernet_management_unconnected_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.ethernet_management_unconnected_pin")'
```
