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

## Conflicting netclass definitions

The following additional tooling-owned settings fixtures exercise two
conflict forms: repeated `net_settings.classes` JSON members, and repeated
`Narrow` class names in one `classes` array. Each conflicting pair contains
0.05 mm and 0.20 mm clearances. KiCad 10.0.8 on the digest-pinned image below
uses the last definition in these cases: the narrow-last faults have no
clearance violation and the wide-last faults have one. The identical-list and
unique-list controls have no clearance violation. Each case was exported twice
with identical violation types; the fixture also reports two
`track_dangling` records in each run.

| Fixture                                     | Conflict form             | Last clearance | Expected clearance result |
| ------------------------------------------- | ------------------------- | -------------: | ------------------------- |
| `fault-netclass-list-narrow-last.kicad_pro` | repeated `classes` member |        0.05 mm | none                      |
| `fault-netclass-list-wide-last.kicad_pro`   | repeated `classes` member |        0.20 mm | one                       |
| `fault-netclass-name-narrow-last.kicad_pro` | repeated class name       |        0.05 mm | none                      |
| `fault-netclass-name-wide-last.kicad_pro`   | repeated class name       |        0.20 mm | one                       |
| `control-identical-netclass-list.kicad_pro` | identical repeated member |        0.05 mm | none                      |
| `control-unique-narrow.kicad_pro`           | unique class list         |        0.05 mm | none                      |

The duplicate-clearance fixtures exercise a third form: two `clearance` keys
inside one `Narrow` class object. The lint reviews differing source values and
keeps identical repeated values quiet. On the same digest-pinned KiCad 10.0.8
image, the last 0.05 mm value yields no clearance violation and the last
0.20 mm value yields one. Each case was exported twice with repeatable
violation types.

| Fixture                                                | Conflict form                | Last clearance | Expected clearance result |
| ------------------------------------------------------ | ---------------------------- | -------------: | ------------------------- |
| `fault-netclass-clearance-narrow-last.kicad_pro`       | duplicate class property     |        0.05 mm | none                      |
| `fault-netclass-clearance-wide-last.kicad_pro`         | duplicate class property     |        0.20 mm | one                       |
| `control-netclass-clearance-duplicate-equal.kicad_pro` | identical duplicate property |        0.05 mm | none                      |

Native image:
`ghcr.io/kicad/kicad:10.0.8-amd64@sha256:05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c`.
This observation is limited to these values, geometry, KiCad version, and image; it does not choose
an intended value or establish an electrical board defect.

| Source                                                 | SHA-256                                                            |
| ------------------------------------------------------ | ------------------------------------------------------------------ |
| `control-identical-netclass-list.kicad_pro`            | `fb8250e2f6670448d2ab6d62bc3df7b4cdcdcfc00a3bbf9c2527e78548d851bb` |
| `fault-netclass-list-narrow-last.kicad_pro`            | `043b28b127bdd202ca96d607f17e0849d2008635ad4d6e27d6700a034ef88943` |
| `fault-netclass-list-wide-last.kicad_pro`              | `ed24748139422924484928b465f86d33666e42571a213964c9c83ab95c30b170` |
| `fault-netclass-name-narrow-last.kicad_pro`            | `71a1fc72400f84d7a3395099487264b357955aa7dd0ba0d7fcc46b835216cf88` |
| `fault-netclass-name-wide-last.kicad_pro`              | `f7f8b1d25d79316c4f8e4c8453246eaed8adbacdefca35b7e7cccf7a1dc92622` |
| `control-netclass-clearance-duplicate-equal.kicad_pro` | `bd78215a548c9a20664cc5f1ff2a22ee820bae518d40af8af9a32d0a7e1451a2` |
| `fault-netclass-clearance-narrow-last.kicad_pro`       | `948b539d30b81112904997f7d8eb6fe9dd47730d7aafdcd590144d652c463b33` |
| `fault-netclass-clearance-wide-last.kicad_pro`         | `cf0517e6b31e2c631942591c3881619626e6fca5a5d12f6b4d798309f2d3ec9f` |

Run the focused source, CLI/MCP, and pinned native regressions with:

```sh
python -I -m pytest -q \
  tests/test_pcb_drc_conflicting_netclass_definitions.py \
  tests/test_design_lint_mcp_parity_pcb_drc_conflicting_netclass_definitions.py \
  -m 'design_lint and pcb_lint and design_lint_rule(rule_id="pcb.drc_conflicting_netclass_definitions")'
KICAD_RUN_NATIVE_PCB_FIXTURES=1 python -I -m pytest -q \
  tests/test_pcb_drc_conflicting_netclass_definitions_native.py \
  -m 'design_lint and pcb_lint and native_kicad and design_lint_rule(rule_id="pcb.drc_conflicting_netclass_definitions")'
```

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
