# Ethernet PHY receive-data and receive-clock output-sharing fixtures

These are tooling-owned synthetic schematics. They contain two passive-typed
`Synthetic:Ethernet_PHY` symbols and no external project or cohort design
source.

| Fixture             | SHA-256                                                            | Expected result                                                                         |
| ------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| `fault.kicad_sch`   | `2da0e7b83d033c59b4056fc976abf32b638aa3f61ee12d2488e3175607c6ea92` | Both PHYs share RXD0 and RXC nets; one REVIEW candidate per rule; no native ERC errors. |
| `control.kicad_sch` | `3f44175e5bf4492bdfc87ea773e2756a1aec83e0e35acbf20458e52993d26bfc` | No same-role RXD or RXC outputs are shared; no candidate; no native ERC errors.         |

The test lane exports each schematic twice with digest-pinned KiCad 10.0.0 and
10.0.5 images, compares normalized netlists and ERC reports, checks both exact
fault/control findings, and records receipts under ignored `build/` output.
Run it with:

```sh
KICAD_RUN_NATIVE_ETHERNET_RX_OUTPUT_SHARING_FIXTURES=1 \
  .venv/bin/python -I -m pytest \
  tests/test_ethernet_rx_output_sharing_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and (design_lint_rule(rule_id="bus.ethernet_rx_outputs_share_net") or design_lint_rule(rule_id="bus.ethernet_rx_clock_outputs_share_net"))'
```

The receive-data predicate recognizes bounded `RXD`/`RXDATA` functions. The
receive-clock predicate recognizes only `RXC`/`RXCLK` with optional MII, GMII,
or RGMII prefixes. Both require explicit bounded Ethernet PHY identity,
complete unique pin inventory, one exact assignment per counted pin, and a
supported output-capable native pin type. Both ask for review; selected or
multiplexed paths may be intentional. The clock rule does not infer PHY mode.
Neither rule proves PHY behavior, MAC topology, PCB copper, or external
connectivity.
