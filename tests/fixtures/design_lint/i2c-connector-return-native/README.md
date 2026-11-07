# Two-pin I2C connector return review fixtures

These tooling-owned schematics are synthetic regression inputs with no external
project or board data.

`fault.kicad_sch` connects a complete generic two-contact connector to native
I2C SDA/SCL pins but exposes no connector return contact. The lint should ask
for reference and pinout review without requiring board ground.
`control.kicad_sch` uses named SDA/SCL contacts and must stay quiet.

The digest-pinned native lane exports both schematics twice with KiCad 10.0.0
and 10.0.5. Source digests are pinned in
`kicad_tooling/ci_hosted_i2c_connector_return_cases.py`.
