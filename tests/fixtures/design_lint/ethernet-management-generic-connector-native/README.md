# Ethernet management generic connector fixtures

These KiCad schematics are synthetic tooling-owned fixtures. The connector
uses generic `Pin_N` contacts, and the PHY uses explicit MDC/MDIO pin
functions. They are independent of customer or project source data.

- `control.kicad_sch` keeps the generic header contacts on separate `PORT_*`
  nets while the PHY management pins remain on `ETH_MDC` and `ETH_MDIO`.
- `fault.kicad_sch` assigns generic connector pins J1.1 and J1.2 to the exact
  PHY `ETH_MDC` and `ETH_MDIO` nets. The resulting candidate asks for connector
  association and pinout review; it does not infer intended use.
The fault finding also reports the remaining native contacts, including the
two AUX pins and J1.5 GND assignment. This is evidence only; it does not require
GND or the AUX pins to be connected in any particular way.

Reviewed SHA-256 values:

- `control.kicad_sch`: `4268403e707494a8f6a021920e442405c13e9217be6afac249b9ece93351ef7f`
- `fault.kicad_sch`: `adcbc744dd2aa12981852f1472190f9a56015cd16e59d8a44305b48e80442a3f`

The native lane exports each source twice with digest-pinned KiCad 10.0.0 and
10.0.5 images. It verifies the exact pins and nets and requires repeatable
normalized netlists. This validates the synthetic rule path and those native
export versions, not electrical intent, PCB connectivity, field precision,
reviewer value, or manufacturing readiness.

```sh
KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_GENERIC_CONNECTOR_FIXTURES=1 \
  KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
  .venv/bin/python -I -m pytest -q \
  tests/test_ethernet_management_generic_connector_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.ethernet_management_generic_connector_pair_review")'
```
