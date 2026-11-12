# Invalid PCB DRC severity-value fixtures

These synthetic project settings cover the exact KiCad 10.0.8 string values
for `board.design_settings.rule_severities`. The fault spells `warning` as
`warnnig` for the known `track_dangling` key. The control uses `warning`.

KiCad's 10.0.8
[`SeverityFromString` implementation](https://docs.kicad.org/doxygen/ui__common_8cpp_source.html)
maps `warning` and `ignore` explicitly and maps every other string to `error`.
The versioned
[`BOARD_DESIGN_SETTINGS` loader](https://gitlab.com/kicad/code/kicad/-/blob/10.0.8/pcbnew/board_design_settings.cpp)
calls that conversion only for recognized DRC keys. Thus a typo in a known
key's value can silently make a warning check an error; it does not suppress
the check. The review asks for settings correction and does not claim a PCB
defect.

The string-value rule applies only to current string-valued keys and the
`hole_near_hole` string migration alias. The separate
`legacy_no_courtyard_defined` and `legacy_courtyards_overlap` aliases are
booleans and remain excluded. This rule is supported only for exact KiCad
10.0.8 until each patch's source and native behavior are audited.
