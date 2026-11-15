# Ethernet management named-rail review fixtures

These source-hashed schematics are synthetic tooling inputs. They use a small
Ethernet PHY and a two-pin management header with explicit MDC/MDIO functions;
they contain no product or customer design data.

- `control.kicad_sch` assigns the header and PHY MDC/MDIO pins to separate
  management-signal nets.
- `fault.kicad_sch` assigns header J2.1 and PHY U1.5 MDC directly to `GND`,
  while their MDIO pins remain on the management-signal net.

Reviewed SHA-256 values:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `a45a5f2054c52cf6a972fd59712944d7ac3a952c4452f2c1d30648a4c6e316ba` |
| `fault.kicad_sch`   | `648fdd77ba46a330a313a7f4929c8a8f89fde89382ba449b47fa17037f6fdbd9` |

The exact-version lane exports both schematics twice with networking disabled
using digest-pinned KiCad 10.0.0 and 10.0.5 images. It checks the pin-function
and net-assignment evidence, repeatable normalized netlists, a quiet control,
and localized REVIEW findings for both the connector and PHY MDC pins on the
fault. It exports netlists only; it does not run ERC or DRC and does not
establish electrical approval or physical connectivity.

```sh
KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_NAMED_RAIL_FIXTURES=1 .venv/bin/python -I -m pytest -q \
  tests/test_ethernet_management_signal_named_rail_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.ethernet_management_signal_on_named_rail")'
```
