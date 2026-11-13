# Empty custom DRC disallow fixtures

These tooling-owned version-1 rules exercise direct `disallow` constraints
with no object operands and controls with one or multiple documented operands.
The source-only check is limited to KiCad 10.0.x and skips rules files that use
`${...}` text-variable substitutions. The unit fault also places two empty
clauses around a valid clause to verify exact constraint ordinals; the native
fault contains only the empty clause.

The
[KiCad 10.0 PCB Editor reference](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#custom-rule-syntax)
specifies one or more object types for `disallow`. On the digest-pinned KiCad 10.0.8 image, the
empty clause completed DRC without an `items_not_allowed` finding, while the one-operand and
multi-operand controls each produced two track disallow findings on the synthetic board. These
observations are limited to the exact fixture sources and image; a review finding does not prove
that a project board violates an electrical or manufacturing requirement.

## Rule-source hashes

| Fixture                              | SHA-256                                                            |
| ------------------------------------ | ------------------------------------------------------------------ |
| `fault-empty-object-list.kicad_dru`  | `fadb99780af4a37058ea47122f417351d0384212c915ee73d2c6a12f2626688a` |
| `fault-native-empty-only.kicad_dru`  | `a35d203cffcb06d5d2b440c95e58d82b8d5dd63dc27c3f554102eb7e77254b7f` |
| `control-one-object.kicad_dru`       | `66ef8dc7297abc716274bbb54e64b3b766ca4c39ee2bbe5bfdf3e70b2dfee2bd` |
| `control-multiple-objects.kicad_dru` | `c709264ad8498dc9e5ff2d8a80dbb36549d25e0bf79afd826f5f977749dce947` |
