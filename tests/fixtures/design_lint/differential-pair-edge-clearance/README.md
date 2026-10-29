# Differential-pair edge-clearance fault and control

These synthetic boards test an authored 1.0 mm minimum copper-to-board-edge
clearance for the exact `USB_D_P` / `USB_D_N` pair. The source is the small
differential-pair board used by LINT-022, with a separate near-edge mutation.

| Fixture             | Track centerlines                                   | Expected native DRC result                     |
| ------------------- | --------------------------------------------------- | ---------------------------------------------- |
| `control.kicad_pcb` | y=10 mm and y=10.5 mm inside a 0–20 mm board height | No `copper_edge_clearance` violation           |
| `fault.kicad_pcb`   | y=0.5 mm and y=1.0 mm beside the y=0 mm board edge  | One or more `copper_edge_clearance` violations |

Both cases use the same `board.kicad_dru` rule and the exact
`A.inDiffPair('USB_D_')` selector. The 1.0 mm threshold is synthetic test data,
not a recommended universal clearance. The test runs each case twice against
the pinned KiCad 10.0.0 and 10.0.5 images and compares the normalized violation
types.

Run the native lane from the tooling checkout:

```sh
KICAD_RUN_NATIVE_PCB_FIXTURES=1 .venv/bin/python -I -m pytest -q \
  -m 'design_lint_rule(rule_id="pcb.differential_pair_rule_coverage")' \
  tests/test_pcb_differential_pair_edge_clearance_native.py
```
