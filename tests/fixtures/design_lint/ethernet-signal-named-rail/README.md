# Ethernet named-rail review fixtures

These source-hashed schematics are synthetic tooling inputs. They describe one
four-pin Ethernet PHY and one RJ45-style connector with explicit TX/RX pair
names; they contain no product or customer design data.

- `control.kicad_sch` assigns the PHY and connector data pins to separate
  Ethernet signal nets.
- `fault.kicad_sch` assigns both U1.1 and J1.1/TDP directly to `GND` and
  preserves the other pair assignments.

Reviewed SHA-256 values:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `0e9470240ffaf003838c22faa1866312dec24c89fcf26130a983185ae015ff16` |
| `fault.kicad_sch`   | `e28ffe084e974c39781e0abee0c65ca0c6452b98dbe3151dcfbd125888466b75` |

The exact-version acceptance lane exports both schematics twice with
networking disabled using digest-pinned KiCad 10.0.0 and 10.0.5 images. It
checks the complete pin-function and net assignment evidence, repeatable
normalized netlists, a quiet control, and REVIEW findings localized to the
connector and PHY fault pins. This demonstrates deterministic label-based review behavior; it does
not establish signal integrity, PHY strap correctness, PCB routing, or
physical connectivity.

```sh
KICAD_RUN_NATIVE_ETHERNET_SIGNAL_NAMED_RAIL_FIXTURES=1 .venv/bin/python -I -m pytest -q \
  tests/test_ethernet_signal_named_rail_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.ethernet_signal_on_named_rail")'
```
