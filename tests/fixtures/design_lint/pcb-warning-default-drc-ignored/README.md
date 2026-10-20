# KiCad warning-default DRC suppression fixtures

These source-hashed `.kicad_pro` files are synthetic tooling fixtures. They
exercise explicit `Ignore` settings for checks whose built-in default is
`Warning` in KiCad 10.0.0, 10.0.3, 10.0.4, 10.0.5, 10.0.6, and 10.0.7, plus a
control that keeps those checks at `Warning` while ignoring unrelated checks.

The supported profile is deliberately exact. Warning defaults are mapped from
`board_design_settings.cpp` and setting keys from `drc_item.cpp` at each listed
KiCad tag. KiCad 10 patch releases can change defaults; this rule must not
extend its profile without checking that version's sources. Versions 10.0.1
and 10.0.2 remain out of scope until their source profiles are verified.

Versioned upstream references:

- [KiCad 10.0.0 board design settings](https://gitlab.com/kicad/code/kicad/-/blob/10.0.0/pcbnew/board_design_settings.cpp)
- [KiCad 10.0.0 DRC setting keys](https://gitlab.com/kicad/code/kicad/-/blob/10.0.0/pcbnew/drc/drc_item.cpp)
- [KiCad 10.0.3 board design settings](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/10.0.3/pcbnew/board_design_settings.cpp)
- [KiCad 10.0.3 DRC setting keys](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/10.0.3/pcbnew/drc/drc_item.cpp)
- [KiCad 10.0.4 board design settings](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/10.0.4/pcbnew/board_design_settings.cpp)
- [KiCad 10.0.4 DRC setting keys](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/10.0.4/pcbnew/drc/drc_item.cpp)
- [KiCad 10.0.5 board design settings](https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/pcbnew/board_design_settings.cpp)
- [KiCad 10.0.5 DRC setting keys](https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/pcbnew/drc/drc_item.cpp)
- [KiCad 10.0.6 board design settings](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/10.0.6/pcbnew/board_design_settings.cpp)
- [KiCad 10.0.6 DRC setting keys](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/10.0.6/pcbnew/drc/drc_item.cpp)
- [KiCad 10.0.7 board design settings](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/10.0.7/pcbnew/board_design_settings.cpp)
- [KiCad 10.0.7 DRC setting keys](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/10.0.7/pcbnew/drc/drc_item.cpp)

The check asks for review of an explicit suppression. It does not establish
that a given check applies to a board, that a violation exists, or that every
project must preserve the native default.
