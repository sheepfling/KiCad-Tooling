# Unknown custom DRC disallow-object fixtures

These tooling-owned version-1 rules share the synthetic board and project in
`pcb-drc-duplicate-net-settings/`. The fault spells `track` as `trak`; the
native control uses the documented `track` operand. A static source control
contains the complete documented KiCad 10.0 disallow vocabulary.

KiCad 10.0 lists the supported disallow object types in the
[PCB Editor reference](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#custom-rule-syntax).
The lint scope is KiCad 10.0.x, with native behavior tested on the
digest-pinned 10.0.8 image. The repeated fault export completed with only two
unrelated `track_dangling` warnings; the valid `track` control added two
`items_not_allowed` errors for the authored rule. This is measured only for
these source files, synthetic board, and exact image. The lint prompts review
for a literal unknown token; it does not validate rule applicability or prove
a PCB defect.

## Source hashes

| Fixture                                      | SHA-256                                                            |
| :------------------------------------------- | :----------------------------------------------------------------- |
| `control-disallow-track.kicad_dru`           | `eaf85d16bc9cf095200132dc7b3ad76548508cdd0f40dac45615070b507fbf43` |
| `control-documentation-vocabulary.kicad_dru` | `28187f5b1c60b364931b4bc25950f218ca3f11bd133476689731cd0df762ff41` |
| `fault-misspelled-track.kicad_dru`           | `fc8674cce9f50113def05e5715ff5eeff0c2d65129528fd8581446b36502f3c1` |
