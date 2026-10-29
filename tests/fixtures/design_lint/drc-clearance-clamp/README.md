# Native copper-edge clearance limit experiment

These tooling-owned synthetic boards measure a 600 mm custom copper-edge
minimum against a 1,200 mm square outline. The two tracks have nominal
edge-to-copper separations of 449.85 mm and 549.85 mm. A native KiCad 10.0.0
or 10.0.5 DRC run reports one edge violation for the 449.85 mm board and
names an effective 500 mm limit. It reports no edge violation for the 549.85 mm
board, despite the authored 600 mm minimum. Both cases are repeated per image.

KiCad's
[`DRC_ENGINE::EvalRules` in 10.0.0](https://gitlab.com/kicad/code/kicad/-/blob/10.0.0/pcbnew/drc/drc_engine.cpp)
and [10.0.5](https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/pcbnew/drc/drc_engine.cpp) clamp
several clearance minima using `MAXIMUM_CLEARANCE`; each version's
[`board_design_settings.h`](https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/include/board_design_settings.h)
defines that value as 500 mm. This fixture establishes only copper-edge
behavior on these pinned versions, and does not approve a physical design.

| Input               | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `board.kicad_dru`   | `2bdbcdf636da79cdca3ac67e60f57520300b8f5dda78cef2c319f359db2e41b2` |
| `board.kicad_pro`   | `eadc610c8422b30f649a19d1f6a1e321eff56686e3bc005b8302a0d996c1ce43` |
| `inside.kicad_pcb`  | `272c4377354b1b6c037fdd2189ec7a01fc9ccfc4478117430cb79c515b9ac66c` |
| `outside.kicad_pcb` | `eb60de363fa5466afe9e175d887ef5e90bc07d969d489677df2e1fb2edfce366` |

Run from the tooling checkout:

```sh
KICAD_RUN_NATIVE_PCB_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_pcb_drc_clearance_clamp_native.py -m 'design_lint and pcb_lint and native_kicad' -q
```
