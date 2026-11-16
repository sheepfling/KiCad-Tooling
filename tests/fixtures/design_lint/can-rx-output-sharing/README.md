# Synthetic CAN receiver-output-sharing fixtures

These tooling-owned schematics contain two explicitly identified synthetic
CAN transceiver modules. The fault joins their passive-typed `CAN_RXD` pins on
`CAN_RX_SHARED`; the control connects one receiver output to a separate
module's `CAN_TXD` pin and leaves the other receiver output on its own net. The
passive pin types keep this review predicate separate from native ERC output
conflict reporting; they do not model real device direction.

The heuristic asks whether the shared receiver path is intentional. It does
not infer module behavior from names, require a particular CAN topology,
establish board copper, or establish off-board wiring. The focused native lane
exports both schematics twice with digest-pinned KiCad 10.0.0 and 10.0.5 images
and checks exact role, identity, assignment, and fitted-state evidence. No
product or proprietary source is included.

Run the synthetic regression with:

```sh
.venv/bin/python -I -m pytest tests/test_can_rx_output_sharing.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.can_rx_outputs_share_net")'
```

Run the Docker native lane with:

```sh
KICAD_RUN_NATIVE_CAN_RX_OUTPUT_SHARING_FIXTURES=1 \
  .venv/bin/python -I -m pytest tests/test_can_rx_output_sharing_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.can_rx_outputs_share_net")'
```

Source SHA-256 digests:

- `shared-receiver-outputs.kicad_sch`
  SHA-256: `e241847190fd65aca9685eb6e2cf036b92732729df7a22c6bf3e7d8b9ba0bd8b`
- `separate-receiver-outputs.kicad_sch`
  SHA-256: `8ff52fcff2091e5200612074f38ba54bf084b0dacece971fd625610e6440ce04`
