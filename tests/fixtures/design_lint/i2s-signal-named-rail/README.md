# I2S signal named-rail fixtures

These tooling-owned schematics exercise `bus.i2s_signal_on_named_rail` with a
synthetic four-pin audio IC. Both schematics carry the same complete I2S pin
inventory; the fault changes only BCLK and data net labels to supply/return-like
names.

| Fixture             | Native assignment                                                        | Expected result            | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------------ | -------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | U1.1 `I2S_BCLK` on `GND`; U1.3 `I2S_DATA` on `+3V3`                      | Two default-REVIEW prompts | `c4612a19cb10cccede0b225dcd78ff7f7c47b812b10e1e72e104b25e1d0a8f2c` |
| `control.kicad_sch` | Bit clock, word select, data, and master clock use neutral separate nets | No finding                 | `ec18ed6db52cf8503718fcdd310d43348d81fa93f13a0ca42b249843889cb189` |

The exact-native lane repeats netlist and ERC exports on digest-pinned KiCad
10.0.0 and 10.0.5 images. It checks tool version, pin functions, assignments,
repeatability, and zero ERC errors. These synthetic schematics establish
source-to-netlist compatibility only; they do not prove I2S use, pinout intent,
electrical potential, field precision, or an electrical requirement.
