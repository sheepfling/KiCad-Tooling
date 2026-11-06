# Ethernet generic connector pair native fixture

This fixture is owned by the tooling repository and contains a synthetic
Ethernet PHY connected to an untyped connector. It is not derived from a
product design.

| Case                | Schematic SHA-256                                                  | Expected `bus.ethernet_generic_connector_pair_review`            |
| ------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------- |
| `control.kicad_sch` | `d2c73ad7a30f2095ef2096723ace951913c2ac13ed6a6bbdf2a8671f76101903` | No finding: generic connector pins are on separate port nets.    |
| `fault.kicad_sch`   | `aa1d5c3ecee3a4a7f84a98e314122a2baf8a7c356b03a980d221d93ff2435198` | Two reviews: generic contacts match the PHY TX pair and RX pair. |

Both cases retain the same complete PHY pin-function inventory. The fault
assigns the generic connector contacts to the PHY data-pair nets; the control
leaves them on separate connector-port nets. The expected findings are
review prompts and do not establish that the connector is Ethernet, that
magnetics or termination are correct, or that PCB copper is continuous.

The native lane uses digest-pinned KiCad 10.0.0 and 10.0.5 images, exports each
case twice, checks the normalized netlist hashes for repeatability, and runs
the catalogued rule against the native netlist.

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_ETHERNET_GENERIC_CONNECTOR_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q \
  tests/test_ethernet_generic_connector_native_fixture_lane.py
```

This verifies deterministic predicate behavior and native-export compatibility
for these synthetic schematics. It does not provide field precision,
reviewer-value, electrical-approval, or manufacturing-readiness evidence.
