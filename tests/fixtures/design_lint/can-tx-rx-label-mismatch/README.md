# Synthetic CAN TX/RX label-direction fixtures

These tooling-owned schematics contain one synthetic CAN controller with
explicit `CAN1_TX` and `CAN1_RX` pin functions. The crossed-label fault assigns
the TX pin to `CAN1_RX` and the RX pin to `CAN1_TX`; the control assigns each
pin to its matching direction label. Passive native pin types keep the fixture
free of unrelated ERC output conflicts.

The opt-in review heuristic compares explicit CAN/FDCAN direction names only.
It does not infer a project pin map, protocol membership, transceiver behavior,
firmware configuration, PCB copper, or off-board wiring. Generic TX/RX and
UART names remain outside the predicate because endpoint naming conventions
vary. No project or cohort source is included.

The native lane repeats netlist and ERC exports with digest-pinned KiCad 10.0.0
and 10.0.5 images. Both schematics must export repeatable netlists without ERC
errors; only the crossed-label fault should produce review findings.

Source SHA-256 digests:

- `crossed-labels.kicad_sch`
  `9d2497c89853798e7dc98451df3f975eadca5ccef45d6c4e229ae65d348c7448`
- `matching-labels-control.kicad_sch`
  `55ad4a1d31d86407edf705955c7bd8fb7d5284784a4376fdcc7da3f89313ee92`
