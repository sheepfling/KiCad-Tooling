# Synthetic CAN TX/RX same-net fixtures

These tooling-owned schematics contain one synthetic CAN controller with
`CAN1_TX` and `CAN1_RX` function pins. `same-net.kicad_sch` connects both pins
to `CAN1_DATA`; `separate-lines-control.kicad_sch` assigns them separate nets.
The pins use passive native electrical types to keep the isolated synthetic
fixture free of unrelated missing-driver warnings. Native electrical type is
not a claim about a real CAN controller; the lint's output-conflict behavior is
covered separately by synthetic typed-netlist tests.

The default-off rule asks whether a same-net loopback or pin assignment is
intentional. It does not infer that all CAN TX and RX pins must be separated,
does not recognize generic UART `TXD`/`RXD` names, and does not establish the
correctness of a project pin map.

The native fixture lane exports both schematics twice and checks stable
netlist and ERC evidence on digest-pinned KiCad 10.0.0 and 10.0.5 images.
No project or cohort source is included.

Source SHA-256 digests:

- `same-net.kicad_sch`
  SHA-256: `f656da266a502a5b4e897240af320b8832de3807a66823ed035b105a33b01baa`
- `separate-lines-control.kicad_sch`
  SHA-256: `d175d4e73ffc11aac75e38651835f36d9420df4ace0d2b709313e114c6fa40c7`
