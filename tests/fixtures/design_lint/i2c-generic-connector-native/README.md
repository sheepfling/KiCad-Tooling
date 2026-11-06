# Generic I2C connector review fixtures

These schematics are synthetic tooling regressions. They contain no external
board or project data.

`fault.kicad_sch` assigns generic connector contacts J1.1 and J1.2 to the exact
I2C_SDA and I2C_SCL nets of fitted U1's native SDA and SCL pins. The heuristic
should request pinout review. `control.kicad_sch` gives the connector explicit
SDA and SCL pin functions on the same nets; the generic-pin heuristic should
stay quiet. Both fixtures also include a ground contact to ensure this rule's
result remains about the signal-pair clue; it does not define a common-ground
requirement.

The digest-pinned KiCad 10.0.0 and 10.0.5 lane exports each source twice,
then compares normalized netlists and lint findings. Source hashes are
registered in `kicad_tooling/ci_hosted_i2c_generic_connector_cases.py`.

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `c05bc388870ce536d9607ef244e1ae1f91614585682c35d273afd47a4ad39e46` |
| `control.kicad_sch` | `506e1b9da8c2479d6c97155247a0bbd7d0b61af062b078c4cb904a3cb1e19459` |
