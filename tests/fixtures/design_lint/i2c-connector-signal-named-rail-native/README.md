# I2C connector signal on named rail

These tooling-owned schematics are synthetic. The control is a tooling copy of
the named SDA/SCL connector arrangement also used by
`i2c-connector-return-native/control.kicad_sch`. The only connectivity
difference is that J1.1's label changes from `I2C_SDA` to `GND`; U1.1 remains
on `I2C_SDA`, and J1.2 and U1.2 remain on `I2C_SCL`. The named-rail rule
should prompt review for J1.1 while remaining quiet for the control.

The existing I2C signal-label lane exports both sources repeatedly with the
digest-pinned KiCad 10.0.0 and 10.0.5 images. This tests native schematic
evidence and repeatability. It does not establish an approved connector
pinout, whether a rail connection is intentional, PCB copper continuity, or
physical connectivity.

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `bf5318dc16afd190043a20423c021312c3fd75f07a2b8bab03a8c9793461428e` |
| `fault.kicad_sch`   | `1eaa12a955dece6deb9f7c8f7af06f9aca5a0f4cd459251fea2ecf3c0bd406f6` |
