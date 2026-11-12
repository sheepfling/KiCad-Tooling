# Duplicate top-level schematic ERC-section fixtures

These tooling-owned settings are paired with `../near-miss-pin-line.kicad_sch`.
They contain no product project source.

| Fixture                          | Root `erc` members   | KiCad 10.0.8 `pin_not_connected` results |
| -------------------------------- | -------------------- | ---------------------------------------- |
| `fault-warning-ignore.kicad_pro` | warning, then ignore | No violations                            |
| `fault-ignore-warning.kicad_pro` | ignore, then warning | Two warnings                             |
| `control-warning.kicad_pro`      | One warning section  | Two warnings                             |
| `control-ignore.kicad_pro`       | One ignore section   | No violations                            |

The observed last-section behavior is specific to the synthetic schematic,
severity key, and digest-pinned KiCad 10.0.8 image. The lint preserves each
repeated section in source order and asks for review; it does not select an
intended section or generalize the native observation to other settings or
KiCad patches.

Run the source-bound check and CLI/MCP parity test with:

```sh
python -I -m pytest -q \
  tests/test_schematic_erc_duplicate_section.py \
  tests/test_design_lint_mcp_parity_schematic_erc_duplicate_section.py \
  -m 'design_lint and schematic_lint and design_lint_rule(rule_id="schematic.erc_duplicate_section")'
```

Run the pinned native fixture with
`KICAD_RUN_NATIVE_SCHEMATIC_ERC_DUPLICATE_SECTION_FIXTURES=1` and the same
rule selector on `tests/test_schematic_erc_duplicate_section_native.py`.
