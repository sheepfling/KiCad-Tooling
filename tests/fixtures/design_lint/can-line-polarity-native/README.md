# Synthetic CAN line-polarity fixtures

The control schematic is the existing tooling-owned split-termination fixture:
[`control.kicad_sch`](../can-split-midpoint-native/control.kicad_sch). The fault
changes only the two net labels at the synthetic CAN interface symbol's
CANH/CANL pins, keeping the pair complete and the net names explicit:
[`reversed-can-lines.kicad_sch`](reversed-can-lines.kicad_sch).

| Case    | Expected result                                                  |
| ------- | ---------------------------------------------------------------- |
| Control | CANH pins use CAN_H and CANL pins use CAN_L; no polarity finding |
| Fault   | U1 CANH is on CAN_L and CANL is on CAN_H; two review findings    |

The control source SHA-256 is
`f69f9084482ce5455740c4ac33628fd226e5243650acd9a2e022984aec830726`. The
fault source SHA-256 is
`7797bca9d15faac4ecd34e870484f32d20229a5c2e2a7699057b15dd1cfc0479`.

The native fixture lane checks the selected project's exact KiCad version and
digest-pinned image, exports each source twice, and evaluates the normalized
netlists with the same design-lint service. It runs against KiCad 10.0.0 and
10.0.5. Outputs and receipts stay under ignored `build/` directories. These
synthetic schematics are not product designs and do not establish physical
line polarity, PCB routing, CAN bus intent, or off-board wiring.

Run the focused native lane from an installed tooling checkout with the public
reference-template checkout available:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_CAN_LINE_POLARITY_FIXTURES=1 \
.venv/bin/python -I -m pytest -q tests/test_can_line_polarity_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.can_line_polarity_label_mismatch")'
```
