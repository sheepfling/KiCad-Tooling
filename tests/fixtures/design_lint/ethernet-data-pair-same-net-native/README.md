# Ethernet same-net complementary-pair native fixtures

These synthetic KiCad schematics exercise the existing
`bus.complementary_pair_assignment` rule on an Ethernet PHY data pair. The
control assigns the fitted PHY TDP/TDN and RDP/RDN pins to four distinct nets.
The fault changes only the TX labels so the positive and negative TX pins
share `ETH_TX_SHARED`. Native electrical types are passive to avoid unrelated
output-conflict ERC findings; they do not describe a real PHY.

The exact-version lane exports both sources twice with the digest-pinned
KiCad 10.0.0 and 10.0.5 images. It verifies stable normalized netlists, exact
pin functions and assignments, and the existing generic rule's finding only
for the fault. No project or cohort source is included.

Run the lane with:

```sh
KICAD_RUN_NATIVE_ETHERNET_DATA_SAME_NET_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q tests/test_ethernet_data_pair_same_net_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.complementary_pair_assignment")'
```
