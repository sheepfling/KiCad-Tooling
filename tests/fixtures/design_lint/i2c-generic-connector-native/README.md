# Generic I2C connector review fixtures

These schematics are synthetic tooling regressions. They contain no external
board or project data.

`fault.kicad_sch` assigns generic connector contacts J1.1 and J1.2 to the exact
I2C_SDA and I2C_SCL nets of fitted U1's native SDA and SCL pins. The heuristic
should request pinout review. Its evidence includes the unassigned VCC contact
and the ground contact assigned to BOARD_GND, without deciding whether either
contact is required or whether grounds should be common. `control.kicad_sch`
gives the connector explicit SDA and SCL pin functions on the same nets while
leaving VCC unassigned; the generic-pin heuristic should stay quiet.

The digest-pinned KiCad 10.0.0 and 10.0.5 lane exports each source twice,
then compares normalized netlists and lint findings. Source hashes are
registered in `kicad_tooling/ci_hosted_i2c_generic_connector_cases.py`.

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `0d8292071410762c81dd447e48e6456d3bf5feb3701c00d2afd74cf91c45f587` |
| `control.kicad_sch` | `096da82167af4feb73c8e69d2d758c55b5f204214b85f367e3ed69e91a7f8e2d` |
