# Native custom-rule text-variable experiment

This tooling-owned synthetic case uses the near-edge fault board in
`../differential-pair-edge-clearance/`. The project defines `KIND` as
`edge_clearance` and `TARGET` as `USB_D_P`. The control has an exact 1 mm
edge rule. Two fault cases add a later ignored rule, substituting either its
constraint type or its net selector through the project variables.

On digest-pinned KiCad 10.0.0 and 10.0.5, each case ran twice: the control
reported at least one copper-edge violation, and both substituted overrides
reported none. The test compares the native results only; no project-specific
requirement or physical design approval follows from this synthetic example.

| Input | SHA-256 |
| --- | --- |
| `../differential-pair-edge-clearance/fault.kicad_pcb` | `a8c166d11f4da490c371981a5e10f99b4daa83e7d93ef47e03099db3a7fa0ffc` |
| `board.kicad_pro` | `c86b6ba3c14b91e9c581e5fcdd7b47503ceec69965874e3c95383f629ac58205` |
| `control.kicad_dru` | `3e0317545b38a59063859e14728ec6b6b488f1ae8c4372696b789d98bfee8051` |
| `type-override.kicad_dru` | `e3bc9b39dca9bdbadb052958aed103ca498074a35560b00a01a02f554358875c` |
| `condition-override.kicad_dru` | `36027adfa8c61b01f7a6f042efadcc1c95776d124bf8aa042a1634824217df59` |

Run from the tooling checkout:

```sh
KICAD_RUN_NATIVE_PCB_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_pcb_drc_text_variables_native.py -m 'design_lint and pcb_lint and native_kicad' -q
```
