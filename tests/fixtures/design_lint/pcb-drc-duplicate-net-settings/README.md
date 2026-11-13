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

| Fixture                                               | Malformed shape                         | Clearance |
| ----------------------------------------------------- | --------------------------------------- | --------- |
| `fault-netclass-classes-object.kicad_pro`             | `classes` is an object                  | one       |
| `fault-netclass-class-entry-null.kicad_pro`           | array item is `null`                    | one       |
| `fault-netclass-class-entry-missing-name.kicad_pro`   | object item has no `name`               | one       |
| `fault-netclass-class-name-null.kicad_pro`            | `name` is `null`                        | one       |
| `fault-netclass-class-name-number.kicad_pro`          | `name` is a number                      | one       |
| `fault-netclass-class-name-boolean.kicad_pro`         | `name` is a boolean                     | one       |
| `fault-netclass-class-name-array.kicad_pro`           | `name` is an array                      | one       |
| `fault-netclass-class-name-object.kicad_pro`          | `name` is an object                     | one       |
| `fault-netclass-class-name-empty.kicad_pro`           | `name` is an empty string               | one       |
| `control-netclass-assignment-default.kicad_pro`       | explicit `Default`                      | one       |
| `control-netclass-assignment-array-narrow.kicad_pro`  | valid `Narrow` array assignment         | none      |

KiCad's 10.0.8 [`NET_SETTINGS` parser][netclass-inventory-source] returns when
`classes` is not an array, then skips entries that are not objects or have no
`name` member. Non-string and empty names also fail to select the fixture's
`Narrow` class. The linter treats these source shapes as review prompts. It
does not validate other class properties or establish the intended constraints.

Native image:
`ghcr.io/kicad/kicad:10.0.8-amd64@sha256:05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c`.
This observation is limited to these values, geometry, KiCad version, and image; it does not choose
an intended value or establish an electrical board defect.

[net-settings-source]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/common/project/net_settings.cpp#L230-263
[netclass-inventory-source]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/common/project/net_settings.cpp#L170-201
[netclass-inventory-name-source]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/common/project/net_settings.cpp#L115-120
[netclass-numeric-conversion]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/common/project/net_settings.cpp#L39-45
[netclass-numeric-fields]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/common/project/net_settings.cpp#L127-149
[net-settings-migration]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/common/project/net_settings.cpp#L418-434

## Malformed netclass names

The class-name fixtures set the `name` field to each JSON type other than a
nonempty string, plus an empty string. KiCad 10.0.8 accepts all six settings
files, but the assigned `Narrow` class is no longer applied: each case has the
same clearance result as the explicit `Default` control. The valid
`control-netclass-assignment-array-narrow.kicad_pro` remains the distinct
control. This confirms a missed inventory shape in the existing malformed
inventory review. It does not show which class a project intended to assign.

The digest-pinned native regression repeats every name fault and both controls
and requires repeatable DRC violation types. This is limited to the synthetic
board, class values, KiCad 10.0.8, and pinned image. KiCad's
[`NET_SETTINGS` class parser][netclass-inventory-name-source] reads the member
as a class name; the observed fallback is specific to the tested CLI behavior.

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
| `fault-netclass-class-name-array.kicad_pro`             | `6a377b2a7d08457dc147d35e66a689dc350c9237a6dda172414ce255aac4a963` |
| `fault-netclass-class-name-boolean.kicad_pro`           | `298a8e6e1b167778cb9e9623f19e3587330bb7243ba072c72510fe4750fdc4a4` |
| `fault-netclass-class-name-empty.kicad_pro`             | `6140e6db6a085f6846f64f0250f415f5c66b09f9eff54f307bf6c3410606a488` |
| `fault-netclass-class-name-null.kicad_pro`              | `a0f276f4499161566a236045eb32f7f53fac47dfc77c023750a513ca00e4d427` |
| `fault-netclass-class-name-number.kicad_pro`            | `200ec98cd810edab141329b4bf7625f9ad2933b9397b7a78c32a16fb5185d51b` |
| `fault-netclass-class-name-object.kicad_pro`            | `19a622f31045059f8b3c37a0683b1fe52a2b292732ec07acd76eb5503a25a4cd` |

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

## Malformed netclass numeric constraint values

These fixtures replace `Narrow.clearance` with each nonnumeric JSON type while
keeping the two `Narrow` assignments. KiCad 10.0.8's numeric conversion helper
uses only JSON numbers for the listed constraint fields. In the pinned native
fixture, every malformed clearance value behaves like explicit `Default`; a
valid numeric Narrow clearance of 0.20 mm produces a clearance violation. The
source rule covers all nine fields, while the native effect comparison is
limited to clearance and this synthetic board.

| Fixture                                                   | `clearance` JSON value | SHA-256                                                            |
| --------------------------------------------------------- | ---------------------- | ------------------------------------------------------------------ |
| `fault-netclass-clearance-type-array.kicad_pro`           | `[]`                   | `3b4868d576f5741659e42a23c10c787626d07ef5e182b08a50d25eb335f5516d` |
| `fault-netclass-clearance-type-boolean.kicad_pro`         | `false`                | `12e4e4050cea56f38ac3adf44990361400d0ef86f83a07e46ba4cd4596a3fb22` |
| `fault-netclass-clearance-type-null.kicad_pro`            | `null`                 | `09bfc7424fab3826f6893b506f08128e1b588db78430618294349a5ea8912bf5` |
| `fault-netclass-clearance-type-object.kicad_pro`          | `{}`                   | `2760e7b5025070b06796c7957c0cf3bd7386d17f5b3712c84f530d1e0cdeb996` |
| `fault-netclass-clearance-type-string.kicad_pro`          | `"0.2"`                | `a5ae5596c3254a6e54ecb1b8641b45fd5612e52f77cc6884f720104dced93269` |
| `control-netclass-clearance-narrower-default.kicad_pro`   | `0.2`                  | `555c72d0dff201be83610eccc608f823cb671fcc49e5e30178e080be598a3bb2` |
| `control-netclass-clearance-default-assignment.kicad_pro` | `0.2`                  | `2f2ca16e74fa331f446195d8345fc37cd01786118ced157b6b05d7e4e63677de` |
| `control-netclass-clearance-property-omitted.kicad_pro`   | omitted                | `c578f1a087127e7765a517b64e19bf6e5da2ee3e233a3b4f5687f749a1188b46` |

The unmatched-pattern rule uses these source-hashed project settings:

| Fixture                         | Pattern assigned to `Narrow` | SHA-256                                                            |
| ------------------------------- | ---------------------------- | ------------------------------------------------------------------ |
| `fault-unmatched.kicad_pro`     | `GHOST`                      | `35abfae4d4c3d4ceb286eee4cd2458a50a19737c4874739875650973cac27ede` |
| `fault-case-mismatch.kicad_pro` | `n1`                         | `ce1892fa119f1dfb4023a7cc327904c56e265be99d75540bbf9edf6615424e14` |
| `control-literal.kicad_pro`     | `N1`                         | `c2b92f4aa1aaa5bb98dfbc54d4190b87d8147518db304e2b360d609882d8d4f3` |
| `control-wildcard.kicad_pro`    | `N*`                         | `321b8fcdc1af338bae910107a9885e2a98702e437f8bd6610eb9e0b644751df3` |
| `control-regex.kicad_pro`       | `N[0-9]+`                    | `7908026a2cb32e45fa7bba59a3c7aede0b09cf9c04b3a3b75f3c470ea4ec6160` |

The DRC regression runs every fault and control twice and requires matching
violation types. The numeric Narrow control reports a clearance violation;
malformed values, explicit Default assignment, and the omitted-property case
do not. This is only an observation for the exact values, geometry, version,
and digest-pinned image below. KiCad source references: [numeric
conversion][netclass-numeric-conversion] and its [netclass field call
sites][netclass-numeric-fields].

Native image:
`ghcr.io/kicad/kicad:10.0.8-amd64@sha256:05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c`.

Run the source and CLI/MCP cases with:

```sh
python -I -m pytest -q \
  tests/test_pcb_drc_malformed_netclass_numeric_constraints.py \
  tests/test_design_lint_mcp_parity_pcb_drc_malformed_netclass_numeric_constraints.py \
  -m 'design_lint and pcb_lint and design_lint_rule(rule_id="pcb.drc_malformed_netclass_numeric_constraints")'
KICAD_RUN_NATIVE_PCB_FIXTURES=1 python -I -m pytest -q \
  tests/test_pcb_drc_malformed_netclass_numeric_constraints_native.py \
  -m 'design_lint and pcb_lint and native_kicad and design_lint_rule(rule_id="pcb.drc_malformed_netclass_numeric_constraints")'
```

## Netclass patterns with no current match

`fault-unmatched.kicad_pro` assigns the valid `GHOST` pattern to the declared
`Narrow` class while the board contains only `N1` and `N2`. The control files
use a matching literal (`N1`), wildcard (`N*`), and regular expression
(`N[0-9]+`). KiCad 10.0.8 applies the Narrow clearance for each matching form;
the unmatched literal and case-mismatched `n1` silently fall back to Default.
The design-lint rule therefore emits a source-bound REVIEW prompt for patterns
with no current board-net match. Reserved patterns for future variants remain
possible and can be suppressed by project policy.

Run the focused source, CLI/MCP, and native regressions with:

```sh
python -I -m pytest -q \
  tests/test_pcb_drc_netclass_pattern_unmatched.py \
  tests/test_design_lint_mcp_parity_pcb_drc_netclass_pattern_unmatched.py \
  -m 'design_lint and pcb_lint and design_lint_rule(rule_id="pcb.drc_netclass_pattern_unmatched")'
KICAD_RUN_NATIVE_PCB_FIXTURES=1 python -I -m pytest -q \
  tests/test_pcb_drc_netclass_pattern_unmatched_native.py \
  -m 'design_lint and pcb_lint and native_kicad and design_lint_rule(rule_id="pcb.drc_netclass_pattern_unmatched")'
```
