# Ethernet PHY output-sharing fixtures

These are tooling-owned synthetic schematics. They contain two passive-typed
`Synthetic:Ethernet_PHY` symbols and no external project or cohort design
source.

| Fixture             | SHA-256                                                            | Expected result                                                                                                               |
| ------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| `fault.kicad_sch`   | `eca30a712a22b7d4f2429168dbda9bca98e122add0e7e2090acdf3245273c3f3` | Both PHYs share RXD0, RXC, RXDV, CRS_DV, CRS, TX_CLK, and COL nets; one REVIEW candidate per rule; no native ERC errors.      |
| `control.kicad_sch` | `3fae0fad8eb15c2f06d4268d69b14fb939f6709f79428a1e098c694b0a8819e5` | No same-role RXD, RXC, RXDV, CRS_DV, CRS, TX_CLK, or COL outputs are shared; no candidate; no native ERC errors.              |

The test lane exports each schematic twice with digest-pinned KiCad 10.0.0 and
10.0.5 images, compares normalized netlists and ERC reports, checks both exact
fault/control findings, and records receipts under ignored `build/` output.
Run it with:

```sh
KICAD_RUN_NATIVE_ETHERNET_RX_OUTPUT_SHARING_FIXTURES=1 \
  .venv/bin/python -I -m pytest \
  tests/test_ethernet_rx_output_sharing_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and (design_lint_rule(rule_id="bus.ethernet_rx_outputs_share_net") or design_lint_rule(rule_id="bus.ethernet_rx_clock_outputs_share_net") or design_lint_rule(rule_id="bus.ethernet_rx_status_outputs_share_net") or design_lint_rule(rule_id="bus.ethernet_crs_dv_outputs_share_net") or design_lint_rule(rule_id="bus.ethernet_crs_outputs_share_net") or design_lint_rule(rule_id="bus.ethernet_tx_clock_outputs_share_net"))'
```

The receive-data predicate recognizes bounded `RXD`/`RXDATA` functions. The
receive-clock predicate recognizes only `RXC`/`RXCLK` with optional MII, GMII,
or RGMII prefixes. The receive-status predicate recognizes `RXDV` and `RXER`
with optional MII or GMII prefixes. Each requires explicit bounded Ethernet
PHY identity, complete unique pin inventory, one exact assignment per counted
pin, and a supported output-capable native pin type. All ask for review;
selected or multiplexed paths may be intentional. The CRS_DV predicate accepts
only `CRS_DV`/`CRSDV` with an optional RMII prefix; the function label does not
prove RMII mode or active output behavior. The MII CRS predicate recognizes
only exact `CRS`/`MII_CRS` names; compound CRS/CRS_DV and CRS/strap labels are
unclassified. The status, clock, CRS_DV, and CRS rules do not infer PHY mode.
The TX_CLK rule recognizes only exact `TX_CLK`/`MII_TX_CLK`; `GTX_CLK`,
`GMII_TX_CLK`, and compound mode/strap labels remain unclassified because the
MII clock-output role does not establish the selected interface mode. None of
the rules proves PHY behavior, MAC topology, PCB copper, or external
connectivity. The MII collision rule recognizes only `COL`/`MII_COL`; TI's
DP83848x example documents COL as an MII collision output used for collision
detection in half-duplex operation. The heuristic does not infer mode,
duplex, active output state, or whether PHY selection makes the shared route
intentional.
