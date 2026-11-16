# Ethernet PHY receive-data, receive-clock, receive-status, and CRS_DV output-sharing fixtures

These are tooling-owned synthetic schematics. They contain two passive-typed
`Synthetic:Ethernet_PHY` symbols and no external project or cohort design
source.

| Fixture             | SHA-256                                                            | Expected result                                                                                        |
| ------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| `fault.kicad_sch`   | `f51976e1303943bf1b185e3cf4711eee3dd57b95eab18432efa3ccf83a2f6194` | Both PHYs share RXD0, RXC, RXDV, and CRS_DV nets; one REVIEW candidate per rule; no native ERC errors. |
| `control.kicad_sch` | `8bcfab6a6486e8c69dff2e13a32135e9942453087e1104945ff9e3cad386bff4` | No same-role RXD, RXC, RXDV, or CRS_DV outputs are shared; no candidate; no native ERC errors.         |

The test lane exports each schematic twice with digest-pinned KiCad 10.0.0 and
10.0.5 images, compares normalized netlists and ERC reports, checks both exact
fault/control findings, and records receipts under ignored `build/` output.
Run it with:

```sh
KICAD_RUN_NATIVE_ETHERNET_RX_OUTPUT_SHARING_FIXTURES=1 \
  .venv/bin/python -I -m pytest \
  tests/test_ethernet_rx_output_sharing_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and (design_lint_rule(rule_id="bus.ethernet_rx_outputs_share_net") or design_lint_rule(rule_id="bus.ethernet_rx_clock_outputs_share_net") or design_lint_rule(rule_id="bus.ethernet_rx_status_outputs_share_net") or design_lint_rule(rule_id="bus.ethernet_crs_dv_outputs_share_net"))'
```

The receive-data predicate recognizes bounded `RXD`/`RXDATA` functions. The
receive-clock predicate recognizes only `RXC`/`RXCLK` with optional MII, GMII,
or RGMII prefixes. The receive-status predicate recognizes `RXDV` and `RXER`
with optional MII or GMII prefixes. Each requires explicit bounded Ethernet
PHY identity, complete unique pin inventory, one exact assignment per counted
pin, and a supported output-capable native pin type. All ask for review;
selected or multiplexed paths may be intentional. The CRS_DV predicate accepts
only `CRS_DV`/`CRSDV` with an optional RMII prefix; the function label does not
prove RMII mode or active output behavior. The status, clock, and CRS_DV rules
do not infer PHY mode. None proves PHY behavior, MAC topology, PCB copper, or
external connectivity.
