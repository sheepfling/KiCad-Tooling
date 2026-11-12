# PCB netclass settings fixtures

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

The netclass-assignment fixtures exercise repeated `N1` keys in one
`netclass_assignments` object. KiCad 10.0.8 applies the final class assignment
in this synthetic case: assigning `N1` to `Narrow` last produces no clearance
violation, while assigning it to `Default` last produces one. An identical
duplicate assignment and the unique assignment are controls. The native test
exports every case twice and checks repeatable DRC violation types.

| Fixture                                                 | Conflict form                  | Last assignment | Expected clearance result |
| ------------------------------------------------------- | ------------------------------ | --------------: | ------------------------- |
| `fault-netclass-assignment-narrow-last.kicad_pro`       | duplicate `N1` assignment      |        `Narrow` | none                      |
| `fault-netclass-assignment-default-last.kicad_pro`      | duplicate `N1` assignment      |       `Default` | one                       |
| `control-netclass-assignment-duplicate-equal.kicad_pro` | identical duplicate assignment |        `Narrow` | none                      |

## Assignments to undeclared netclasses

The unresolved-assignment cases use the same synthetic two-track PCB. The
faults assign `N1` to either an undeclared `MissingClass` or the case-mismatched
name `narrow`, while the declared class is `Narrow`. KiCad 10.0.8 applies the
same 0.20 mm clearance as an explicit `Default` assignment; both fault forms
produce one clearance violation. The `Default` control produces the same native
DRC result without a lint finding, while the declared `Narrow` control has no
clearance violation. The exact source rule uses the class names as written and
does not recommend a replacement class.

The native regression repeats the undeclared and case-mismatched faults, the
explicit `Default` control, and the valid `Narrow` control using the digest-
pinned image below. This measures only these settings, values, board geometry,
KiCad 10.0.8, and image; it does not establish an electrical board defect.

Current KiCad settings store each net's assignments as an array of class
names. The tooling-owned array cases set `net_settings.meta.version` to 5.
An array containing only `MissingClass` produces the same clearance finding as
the explicit `Default` control. An array containing `Narrow` and
`MissingClass` keeps the Narrow clearance behavior but still receives a
source-bound review for the unresolved member. A declared `Narrow` array and an
empty array are controls. This confirms that the lint reports unknown members
without claiming that the entire mixed assignment falls back to Default.
The KiCad 10.0.8 [`NET_SETTINGS` parser][net-settings-source] iterates the
class-name array and stores each name; its [legacy schema migration][net-settings-migration]
wraps an old scalar assignment in an array.

## Malformed netclass assignment shapes

The malformed-shape cases probe supported KiCad 10.0.8 behavior on the same
two-track board. An array containing `Narrow` and `null`, a numeric per-net
assignment, and a non-object assignment map each produce the same clearance
result as the explicit `Default` control. The valid `Narrow` array remains free
of a clearance violation. The native regression repeats each fault and both
controls and checks that the DRC result is stable. This evidence is limited to
these JSON shapes, class values, board geometry, and the pinned image; it does
not establish the intended class on another project.

The parser source shows that KiCad reads `netclass_assignments` only as an
object and then converts each iterated assignment value to a string. A legacy
schema migration wraps scalar strings in arrays. The lint reports malformed
source shape for review; it does not select a class or claim every malformed
value has the same behavior.

## Malformed netclass inventory shapes

The classes fixtures probe three shapes that KiCad 10.0.8 skips while loading
its netclass inventory: `classes` as an object, a `null` array entry, and an
object entry without `name`. Each produces the same clearance violation as the
explicit `Default` control; the valid `Narrow` control has no clearance
violation. The native regression repeats each case and both controls. This is
bounded to the exact settings, board, version, and image below. The source
review reports the malformed location and JSON type; it does not infer a
replacement class.

| Fixture                                              | Malformed shape                 | Clearance |
| ---------------------------------------------------- | ------------------------------- | --------- |
| `fault-netclass-classes-object.kicad_pro`            | `classes` is an object          | one       |
| `fault-netclass-class-entry-null.kicad_pro`          | array item is `null`            | one       |
| `fault-netclass-class-entry-missing-name.kicad_pro`  | object item has no `name`       | one       |
| `control-netclass-assignment-default.kicad_pro`      | explicit `Default`              | one       |
| `control-netclass-assignment-array-narrow.kicad_pro` | valid `Narrow` array assignment | none      |

KiCad's 10.0.8 [`NET_SETTINGS` parser][netclass-inventory-source] returns when
`classes` is not an array, then skips entries that are not objects or have no
`name` member. The linter treats those as review prompts. It does not validate
other class properties or establish the intended constraints.

Native image:
`ghcr.io/kicad/kicad:10.0.8-amd64@sha256:05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c`.
This observation is limited to these values, geometry, KiCad version, and image; it does not choose
an intended value or establish an electrical board defect.

[net-settings-source]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/common/project/net_settings.cpp#L230-263
[netclass-inventory-source]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/common/project/net_settings.cpp#L170-201
[net-settings-migration]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/common/project/net_settings.cpp#L418-434

| Source                                                  | SHA-256                                                            |
| ------------------------------------------------------- | ------------------------------------------------------------------ |
| `control-identical-netclass-list.kicad_pro`             | `fb8250e2f6670448d2ab6d62bc3df7b4cdcdcfc00a3bbf9c2527e78548d851bb` |
| `fault-netclass-list-narrow-last.kicad_pro`             | `043b28b127bdd202ca96d607f17e0849d2008635ad4d6e27d6700a034ef88943` |
| `fault-netclass-list-wide-last.kicad_pro`               | `ed24748139422924484928b465f86d33666e42571a213964c9c83ab95c30b170` |
| `fault-netclass-name-narrow-last.kicad_pro`             | `71a1fc72400f84d7a3395099487264b357955aa7dd0ba0d7fcc46b835216cf88` |
| `fault-netclass-name-wide-last.kicad_pro`               | `f7f8b1d25d79316c4f8e4c8453246eaed8adbacdefca35b7e7cccf7a1dc92622` |
| `control-netclass-clearance-duplicate-equal.kicad_pro`  | `bd78215a548c9a20664cc5f1ff2a22ee820bae518d40af8af9a32d0a7e1451a2` |
| `fault-netclass-clearance-narrow-last.kicad_pro`        | `948b539d30b81112904997f7d8eb6fe9dd47730d7aafdcd590144d652c463b33` |
| `fault-netclass-clearance-wide-last.kicad_pro`          | `cf0517e6b31e2c631942591c3881619626e6fca5a5d12f6b4d798309f2d3ec9f` |
| `fault-netclass-assignment-narrow-last.kicad_pro`       | `8aeab58637966ab9ad5f2925d59ff1ce8ca04cb63d6b8bea6ee144770a2e79f5` |
| `fault-netclass-assignment-default-last.kicad_pro`      | `e8531dd55e82dddcce31e00426eee90c891f747ba511c070b3c1ccd54da4fad5` |
| `control-netclass-assignment-duplicate-equal.kicad_pro` | `ecba7e55a0007d875ead0bfbf675c124680434343300dcaf46dc20c46fec57d8` |
| `fault-netclass-assignment-undeclared.kicad_pro`        | `19df5a0b5492c549612e921c00e13a36e0ff0b4a56b79e881434c361acd202dd` |
| `fault-netclass-assignment-case-mismatch.kicad_pro`     | `c9f6b01751f80d867a8c1b45f6ddc236afe44751da31d6464ba50b287ff73551` |
| `control-netclass-assignment-default.kicad_pro`         | `f6a4b45a1be90581b0449355151325138ab0e9c4e6a3252bf0d602577901e467` |
| `fault-netclass-assignment-array-undeclared.kicad_pro`  | `0b82fbd7a2cae5413427c493964ac8a03c948d598cb6dea4876180bf37a4edf0` |
| `fault-netclass-assignment-array-mixed.kicad_pro`       | `567b9e54335359274b2fe1a42dacdf5542fcf87ec44fdee78c2219ed4e48c76d` |
| `control-netclass-assignment-array-narrow.kicad_pro`    | `8945d702eb8f5b7e1b1fb7b78d24798445b48858daf36a3a8e2ba10491d5fa88` |
| `control-netclass-assignment-array-empty.kicad_pro`     | `6f94553a84c3b85ad642bf7cc12e4a198d824f9c35bb87c0044ecbe61735d0ca` |
| `fault-netclass-assignment-array-nonstring.kicad_pro`   | `30dc2a9893349267ee687712d42f46bf3e34f228f863560fd280699356820c78` |
| `fault-netclass-assignment-value-number.kicad_pro`      | `d25e8ef51e4057815a4b8c0c560e1f28a0309969df891000a8b84df7b7117c87` |
| `fault-netclass-assignment-map-array.kicad_pro`         | `f7b10a8cad4c0e305b61e50b43009ea25e9d52a077e96421d9a8fcec62dc026c` |
| `fault-netclass-classes-object.kicad_pro`               | `c53ce061e4b5718bd5145851d59210036381dbb87e62b1e9993d6da9a3544136` |
| `fault-netclass-class-entry-null.kicad_pro`             | `edcd031ad5bb8db7d79d003a09fd572bb0a2088da3c2963d6c5af4b79d575edf` |
| `fault-netclass-class-entry-missing-name.kicad_pro`     | `f7cdfb2ed83f4c9d756e8ce324501149a3bae098952517e8c3038afdaef7281d` |

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

Run the unresolved-netclass source and CLI/MCP regressions with:

```sh
python -I -m pytest -q \
  tests/test_pcb_drc_unresolved_netclass_assignment.py \
  tests/test_design_lint_mcp_parity_pcb_drc_unresolved_netclass_assignment.py \
  -m 'design_lint and pcb_lint and design_lint_rule(rule_id="pcb.drc_unresolved_netclass_assignment")'
KICAD_RUN_NATIVE_PCB_FIXTURES=1 python -I -m pytest -q \
  tests/test_pcb_drc_unresolved_netclass_assignment_native.py \
  -m 'design_lint and pcb_lint and native_kicad and design_lint_rule(rule_id="pcb.drc_unresolved_netclass_assignment")'
```

Run the malformed-assignment source and CLI/MCP regressions with:

```sh
python -I -m pytest -q \
  tests/test_pcb_drc_malformed_netclass_assignment.py \
  tests/test_design_lint_mcp_parity_pcb_drc_malformed_netclass_assignment.py \
  -m 'design_lint and pcb_lint and design_lint_rule(rule_id="pcb.drc_malformed_netclass_assignment")'
KICAD_RUN_NATIVE_PCB_FIXTURES=1 python -I -m pytest -q \
  tests/test_pcb_drc_malformed_netclass_assignment_native.py \
  -m 'design_lint and pcb_lint and native_kicad and design_lint_rule(rule_id="pcb.drc_malformed_netclass_assignment")'
python -I -m pytest -q \
  tests/test_pcb_drc_malformed_netclass_inventory.py \
  tests/test_design_lint_mcp_parity_pcb_drc_malformed_netclass_inventory.py \
  -m 'design_lint and pcb_lint and design_lint_rule(rule_id="pcb.drc_malformed_netclass_inventory")'
KICAD_RUN_NATIVE_PCB_FIXTURES=1 python -I -m pytest -q \
  tests/test_pcb_drc_malformed_netclass_inventory_native.py \
  -m 'design_lint and pcb_lint and native_kicad and design_lint_rule(rule_id="pcb.drc_malformed_netclass_inventory")'
```
