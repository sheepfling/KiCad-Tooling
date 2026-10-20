# Miscellaneous DRC severity fixtures

These tooling-owned KiCad 10.0 project-settings fragments exercise the nine
Error-default miscellaneous DRC settings covered by the rule:
`footprint`, `item_on_disabled_layer`, `items_not_allowed`,
`npth_inside_courtyard`, `pth_inside_courtyard`, `text_on_edge_cuts`,
`through_hole_pad_without_hole`, `unresolved_variable`, and `zones_intersect`.

- `fault.kicad_pro` assigns Warning or Ignore to each covered check and should
  yield nine source-bound review candidates.
- `control.kicad_pro` keeps all covered checks at Error while changing other
  severity settings, including default-Warning and default-Ignore checks. It
  should yield no candidate for this rule.

The source confirms `text_on_edge_cuts` as an editable severity key with the
Error default; the KiCad 10 manual does not list it in the miscellaneous table.
The rule reviews an explicit severity change only. No board, project design,
or KiCad source is stored here, and the fixtures do not claim a DRC violation.
