# Ethernet management named-rail review fixtures

These source-hashed schematics are synthetic tooling inputs. They use a small
Ethernet PHY symbol with explicit MDC/MDIO functions and contain no product or
customer design data.

- `control.kicad_sch` assigns MDC and MDIO to separate management-signal nets.
- `fault.kicad_sch` assigns MDC directly to `GND` and leaves MDIO on its
  management-signal net.

Reviewed SHA-256 values:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `3ddd8d2919eade8a6bb8f7a8c059dafbe9b348aacbb5a6bb8398b0c62944d31b` |
| `fault.kicad_sch`   | `6ab770da2bd563b08152d89a12f10f1eb872550233815e3f1b398c4e290fc86a` |

The exact-version lane exports both schematics twice with networking disabled
using digest-pinned KiCad 10.0.0 and 10.0.5 images. It checks the pin-function
and net-assignment evidence, repeatable normalized netlists, a quiet control,
and one localized REVIEW finding on the fault. It exports netlists only; it
does not run ERC or DRC and does not establish electrical approval or physical
connectivity.

```sh
KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_NAMED_RAIL_FIXTURES=1 .venv/bin/python -I -m pytest -q \
  tests/test_ethernet_management_signal_named_rail_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.ethernet_management_signal_on_named_rail")'
```
