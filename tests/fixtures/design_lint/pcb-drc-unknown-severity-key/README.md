# Unknown PCB DRC severity key fixtures

These synthetic project settings exercise the exact KiCad 10.0.8 serialized
`board.design_settings.rule_severities` key boundary. The fault contains a
misspelled `track_dangling_typo` key alongside a recognized `track_dangling`
warning. The control uses the recognized key with `ignore`.

KiCad 10.0.8 applies saved severities by matching the configured key against
its registered DRC item IDs. Unknown keys are skipped when project settings are
loaded. The exact recognized keys are derived from
[`DRC_ITEM::allItemTypes`](https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/pcbnew/drc/drc_item.cpp)
and the severity loader in
[`BOARD_DESIGN_SETTINGS`](https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/pcbnew/board_design_settings.cpp).
The versioned [`GetItemsWithSeverities` registry][drc-item-header] ends at the
internal heading. The settings loader also handles three legacy aliases before
loading current severity keys, and those aliases are treated as recognized
settings.

The native regression runs the tooling-owned
`pcb-reference-zone-island/fault.kicad_pcb` board in the digest-pinned KiCad
10.0.8 container. The typo leaves the dangling-track warning visible; the
recognized `track_dangling=ignore` control suppresses it. This verifies key
loading behavior only. It does not identify the intended key for a project or
claim a board defect.

[drc-item-header]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/pcbnew/drc/drc_item.h
