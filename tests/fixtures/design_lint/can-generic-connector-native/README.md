# Generic CAN connector review fixtures

These small schematics are synthetic tooling regressions and do not copy any
external project board data.

`fault.kicad_sch` assigns generic connector pins J1.1 and J1.2 to the exact
CAN_H and CAN_L nets of the fitted U1 symbol's native CANH and CANL pins. The
heuristic should request a pinout review. Its evidence includes the unassigned
VCC contact and the GND contact assigned to BOARD_GND; it does not decide
whether either contact is required or whether references should be common.

`control.kicad_sch` uses named CANH and CANL connector pins on the same bus
while leaving VCC unassigned. The generic-pin heuristic should stay quiet.

The digest-pinned KiCad 10.0.0 and 10.0.5 lane exports each source twice and
compares normalized netlists and lint findings. Source hashes are registered
in `kicad_tooling/ci_hosted_can_generic_connector_cases.py`.

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `b70560940aeec2baf120bea51ffbc5bd45ea7bed65b5c285e45f218602dc6112` |
| `control.kicad_sch` | `9bb6e5f00617cc1b6b3f76acc4ac9c0090eb2101fca107bbc9c022bb278aaeaa` |
