# Duplicate top-level PCB net_settings fixtures

These are tooling-owned synthetic inputs. The PCB contains two parallel,
unconnected tracks on `N1` and `N2`; both nets are assigned to the `Narrow`
netclass in each settings case. The 0.10 mm edge spacing makes 0.05 mm and
0.20 mm netclass clearances produce distinguishable native DRC results.

| Fixture                           | Root `net_settings` values | Expected clearance result |
| --------------------------------- | -------------------------- | ------------------------- |
| `fault-narrow-last.kicad_pro`     | 0.20 mm, then 0.05 mm      | No clearance violation    |
| `fault-wide-last.kicad_pro`       | 0.05 mm, then 0.20 mm      | One clearance violation   |
| `control-unique-narrow.kicad_pro` | One 0.05 mm section        | No clearance violation    |

Digest-pinned KiCad 10.0.8 DRC confirms the last duplicate section controls
the class clearance in this fixture. The repeated-section lint retains source
order and requests review; it does not select a value or run against adopter
boards. The result is limited to this netclass setting and exact image.

## Fixture source hashes

| Source                            | SHA-256                                                            |
| --------------------------------- | ------------------------------------------------------------------ |
| `board.kicad_pcb`                 | `47914e5502c7b022fba5802c3d8391d636bf5e0fffd672eccb36f281adaecff3` |
| `control-unique-narrow.kicad_pro` | `b3454f740108fb5766783688962e00b9831ff4fb0ca18f4bb4d2e5cfdbc98de5` |
| `fault-narrow-last.kicad_pro`     | `eda25107d816187358c3fe9c4123964177319cf365d6f1280a2c58015a8139d5` |
| `fault-wide-last.kicad_pro`       | `df11aa162318b4ab52ded878295d822614af55102faf187907ae3eb4fe58adfd` |

Run the source-bound and CLI/MCP regressions with:

```sh
python -I -m pytest -q \
  tests/test_pcb_drc_duplicate_net_settings_section.py \
  tests/test_design_lint_mcp_parity_pcb_drc_duplicate_net_settings_section.py \
  -m 'design_lint and pcb_lint and design_lint_rule(rule_id="pcb.drc_duplicate_net_settings_section")'
```

Run the exact-version native regression with
`KICAD_RUN_NATIVE_PCB_FIXTURES=1` and the same rule selector on
`tests/test_pcb_drc_duplicate_net_settings_section_native.py`.
