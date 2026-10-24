# Native CAN/FDCAN unconnected-direction fixture

These schematics are synthetic regression inputs owned by KiCad Team Tooling.
They contain no product design or cohort source and are marked not for
manufacture.

| Fixture             | Expected result                                                                                      |
| ------------------- | ---------------------------------------------------------------------------------------------------- |
| `control.kicad_sch` | U1 and U2 each expose assigned `CAN1_TX` and `CAN1_RX` functions; no open-direction finding.         |
| `open-tx.kicad_sch` | U1.1 is explicitly no-connect while U1.2 remains assigned to `CAN1_RX`; review identifies only U1.1. |

The exact-version fixture lane exports both sources twice using digest-pinned
KiCad 10.0.0 and 10.0.5. It checks the native function inventory, component pin
numbers, and exact CAN net assignments before comparing normalized typed
netlists and the default-off/review reports. The open TX pin remains a review
candidate because a receive-only channel may be intentional.

Run from the tooling checkout after installing its development environment and
setting `KICAD_TEMPLATE_ROOT` to a public template checkout:

```sh
KICAD_RUN_NATIVE_CAN_UNCONNECTED_DIRECTION_PIN_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest tests/test_can_unconnected_direction_pins_native_fixture_lane.py \
    -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.can_unconnected_direction_pin")'
```

Pinned source hashes:

- `control.kicad_sch`: `3333488238d746ef18c6ace63e6b3cd0e65f1b48c7aca959f4edf76d561baaf7`
- `open-tx.kicad_sch`: `e653fe6f2c2dc9378b4a410212320706481ba5d1f78bd991acd1ec745ee1a3d6`

Receipts and native exports are written only under ignored `build/` paths. A
passing run verifies native netlist parsing and deterministic rule behavior; it
does not establish firmware configuration, PCB copper, external wiring, or
engineering approval.
