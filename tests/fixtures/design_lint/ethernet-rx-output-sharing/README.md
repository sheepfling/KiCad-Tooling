# Ethernet PHY receive-data, receive-clock, and receive-status output-sharing fixtures

These are tooling-owned synthetic schematics. They contain two passive-typed
`Synthetic:Ethernet_PHY` symbols and no external project or cohort design
source.

| Fixture             | SHA-256                                                            | Expected result                                                                                |
| ------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `fault.kicad_sch`   | `b338af0a3373c57c2f636c44eb3ae8e5e05764fe16590a77cae6043da25af82e` | Both PHYs share RXD0, RXC, and RXDV nets; one REVIEW candidate per rule; no native ERC errors. |
| `control.kicad_sch` | `bee79ef0035f002944aeaf2453c398aebd101c2a39493d6cb73f04890f448d79` | No same-role RXD, RXC, or RXDV outputs are shared; no candidate; no native ERC errors.         |

The test lane exports each schematic twice with digest-pinned KiCad 10.0.0 and
10.0.5 images, compares normalized netlists and ERC reports, checks both exact
fault/control findings, and records receipts under ignored `build/` output.
Run it with:

```sh
KICAD_RUN_NATIVE_ETHERNET_RX_OUTPUT_SHARING_FIXTURES=1 \
  .venv/bin/python -I -m pytest \
  tests/test_ethernet_rx_output_sharing_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and (design_lint_rule(rule_id="bus.ethernet_rx_outputs_share_net") or design_lint_rule(rule_id="bus.ethernet_rx_clock_outputs_share_net") or design_lint_rule(rule_id="bus.ethernet_rx_status_outputs_share_net"))'
```

The receive-data predicate recognizes bounded `RXD`/`RXDATA` functions. The
receive-clock predicate recognizes only `RXC`/`RXCLK` with optional MII, GMII,
or RGMII prefixes. The receive-status predicate recognizes `RXDV` and `RXER`
with optional MII or GMII prefixes. Each requires explicit bounded Ethernet
PHY identity, complete unique pin inventory, one exact assignment per counted
pin, and a supported output-capable native pin type. All ask for review;
selected or multiplexed paths may be intentional. The status and clock rules
do not infer PHY mode. None proves PHY behavior, MAC topology, PCB copper, or
external connectivity.
