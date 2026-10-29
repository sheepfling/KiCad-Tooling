# Native custom-rule severity text variable

This tooling-owned experiment uses the near-edge synthetic board at
`../differential-pair-edge-clearance/fault.kicad_pcb`. All cases use the same
custom rule, whose severity is `${MODE}`. The three project files set `MODE` to
`error`, `ignore`, and `exclusion` respectively; the rule requires 1 mm edge
clearance for `USB_D_P`.

The digest-pinned KiCad 10.0.0 and 10.0.5 images ran each case twice. The
error case produced one copper-edge violation and the ignore case produced
none. The exclusion case produced one violation in both versions; the 10.0.5
JSON record carried `excluded: true`, while the 10.0.0 record did not carry
that marker. These results describe this synthetic fixture and do not establish
the intent or physical suitability of another design. The test runs native
KiCad only; it does not exercise the tooling's severity-review analyzer.

| Input                                                 | SHA-256                                                            |
| ----------------------------------------------------- | ------------------------------------------------------------------ |
| `../differential-pair-edge-clearance/fault.kicad_pcb` | `a8c166d11f4da490c371981a5e10f99b4daa83e7d93ef47e03099db3a7fa0ffc` |
| `board.kicad_dru`                                     | `e6277f1e0de7580e8f3e4cd83c23ae9c13fc4471195f4db0d5233d62db60d476` |
| `error.kicad_pro`                                     | `f4e5e80804ad57f87a593aa8c5f5ecc16047d93ff7e40845747691269bb16453` |
| `ignore.kicad_pro`                                    | `0b39c2298e6f66cbc43e314e7d47ed67afa01360de5badcd3a8ae83228f85389` |
| `exclusion.kicad_pro`                                 | `56e8f95f4b3b748a4c98b71f4bdcbda80ef0ceb5a206b09f7341bf120e6c9518` |

Run from the tooling checkout:

```sh
KICAD_RUN_NATIVE_PCB_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_pcb_drc_severity_text_variable_native.py -m 'design_lint and pcb_lint and native_kicad' -q
```
