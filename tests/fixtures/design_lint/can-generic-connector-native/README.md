# Generic CAN connector review fixtures

These small schematics are synthetic tooling regressions and do not copy any
external project board data.

`fault.kicad_sch` assigns generic connector pins J1.1 and J1.2 to the exact
CAN_H and CAN_L nets of the fitted U1 symbol's native CANH and CANL pins. The
heuristic should request a pinout review.

`control.kicad_sch` uses named CANH and CANL connector pins on the same bus.
The generic-pin heuristic should stay quiet.

The digest-pinned KiCad 10.0.0 and 10.0.5 lane exports each source twice and
compares normalized netlists and lint findings. Source hashes are registered
in `kicad_tooling/ci_hosted_can_generic_connector_cases.py`.

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `b2b88fe7275b176ce214b3723d83844bc71549770ebcdfc3f278ba5792a4cc13` |
| `control.kicad_sch` | `2706180c46a92b65bf3055050873e8d9104d43bf88d04b1131cd826ffde818da` |
