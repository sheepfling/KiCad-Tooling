# Ethernet PHY receive-data output-sharing fixtures

These are tooling-owned synthetic schematics. They contain two passive-typed
`Synthetic:Ethernet_PHY` symbols and no external project or cohort design
source.

| Fixture             | SHA-256                                                            | Expected result                                                                   |
| ------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| `fault.kicad_sch`   | `1d78b669cc9b320b3eacd4b1bd74feeb1de0c6300fcaea795a5f195b877e5dca` | U1.1 and U2.1 share `ETH_RXD_SHARED`; one REVIEW candidate; no native ERC errors. |
| `control.kicad_sch` | `ed421c7f626734649f69560340b94184668e888e221e55def18ee476f2f290eb` | RX data outputs are on separate nets; no candidate; no native ERC errors.         |

The test lane exports each schematic twice with digest-pinned KiCad 10.0.0 and
10.0.5 images, compares normalized netlists and ERC reports, checks the exact
fault/control findings, and records receipts under ignored `build/` output.
Run it with:

```sh
KICAD_RUN_NATIVE_ETHERNET_RX_OUTPUT_SHARING_FIXTURES=1 \
  .venv/bin/python -I -m pytest \
  tests/test_ethernet_rx_output_sharing_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.ethernet_rx_outputs_share_net")'
```

The predicate requires explicit bounded Ethernet PHY identity, complete unique
pin inventory, one exact assignment per output, and a supported output-capable
native pin type. It asks for review; a muxed or selected path may be
intentional. Neither the schematic nor this heuristic proves PHY behavior,
MAC topology, PCB copper, or external connectivity.
