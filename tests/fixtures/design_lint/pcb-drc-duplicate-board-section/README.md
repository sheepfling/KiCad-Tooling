# Duplicate top-level PCB board-section fixtures

These tooling-owned project settings use the synthetic dangling-track board
from `../pcb-reference-zone-island/fault.kicad_pcb`. They contain no product
project source.

| Fixture                            | Repeated root member                          | Expected native `track_dangling` result |
| ---------------------------------- | --------------------------------------------- | --------------------------------------- |
| `fault-ignore-last.kicad_pro`      | `board`: warning section, then ignore section | No violations                           |
| `fault-warning-last.kicad_pro`     | `board`: ignore section, then warning section | Warning violations                      |
| `control-unique-warning.kicad_pro` | One warning section                           | Warning violations                      |

KiCad 10.0.8 is observed applying the last root `board` member in this fixture.
That native result is specific to the `track_dangling` severity setting and the
digest-pinned image. The lint retains each duplicate section in source order,
reports the exact project source hash, and asks for review. It does not choose
an intended section or generalize the observation to other settings or KiCad
patches.

## Fixture source hashes

| Source                                                                | SHA-256                                                            |
| --------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `fault-ignore-last.kicad_pro`                                         | `6814d6eeffe748c24dde28d1c1660a8b4e22d3aea834be53ead0eaa6f547c768` |
| `fault-warning-last.kicad_pro`                                        | `d6403d218638760e710a616a1e830036a5cd220ce23e011cf442ca33808c0eee` |
| `control-unique-warning.kicad_pro`                                    | `760150532fa738733922d7e9ba62a964160d7ef2cdd2e732ab32d221081bca90` |
| Shared synthetic board `../pcb-reference-zone-island/fault.kicad_pcb` | `501f69644d4f40dae7f2aada3da27595cfb2d32aae8b2213e2909d76c46115d4` |

Run the source-bound check and parity tests with:

```sh
python -I -m pytest -q \
  tests/test_pcb_drc_duplicate_board_section.py \
  tests/test_design_lint_mcp_parity_pcb_drc_duplicate_board_section.py \
  -m 'design_lint and pcb_lint and design_lint_rule(rule_id="pcb.drc_duplicate_board_section")'
```

Run the pinned native fixture with `KICAD_RUN_NATIVE_PCB_FIXTURES=1` and the
same rule selector on `tests/test_pcb_drc_duplicate_board_section_native.py`.
Receipts remain under ignored `build/` directories.
