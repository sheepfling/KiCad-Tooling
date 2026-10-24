# Ethernet named-rail review fixtures

These source-hashed schematics are synthetic tooling inputs. They describe one
four-pin Ethernet PHY with explicit TX/RX pair names; they contain no product
or customer design data.

- `control.kicad_sch` assigns all four PHY data pins to separate Ethernet
  signal nets.
- `fault.kicad_sch` assigns the PHY's `TDP` pin directly to `GND` and preserves
  the other three pair assignments.

Reviewed SHA-256 values:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `b8460f781f7f3ef341b375656ae487ed926cd3a3824098180c5b7460fe61fecd` |
| `fault.kicad_sch`   | `1db5c1e1efa99eaf09df7f9a853fe37f4c621afb56481ccc7f909fa0d96c3531` |

The exact-version acceptance lane exports both schematics twice with
networking disabled using digest-pinned KiCad 10.0.0 and 10.0.5 images. It
checks the complete pin-function and net assignment evidence, repeatable
normalized netlists, a quiet control, and one localized REVIEW finding on the
fault. This demonstrates deterministic label-based review behavior; it does
not establish signal integrity, PHY strap correctness, PCB routing, or
physical connectivity.

```sh
KICAD_RUN_NATIVE_ETHERNET_SIGNAL_NAMED_RAIL_FIXTURES=1 .venv/bin/python -I -m pytest -q \
  tests/test_ethernet_signal_named_rail_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.ethernet_signal_on_named_rail")'
```
