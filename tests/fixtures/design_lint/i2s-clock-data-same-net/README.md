# I2S clock/data same-net fixtures

These tooling-owned schematics exercise `bus.i2s_clock_data_same_net` using
an embedded synthetic four-pin audio IC symbol. They contain no product board,
connector pinout, or project expectation.

| Fixture             | Native assignment                                          | Expected result           | SHA-256                                                            |
| ------------------- | ---------------------------------------------------------- | ------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | U1.1 `I2S_BCLK` and U1.3 `I2S_DATA` share `I2S_SHARED`     | One default-REVIEW prompt | `eef6552c8ff6362b2bdc86e10b1ca2c541894102fab993c42fe0011813a97d83` |
| `control.kicad_sch` | Bit clock and serial data use separate nets                | No finding                | `5f6dab83fbd594418b23b8c086c074e48ef1f4663d7cf0fb0140b75e3fa849f7` |

The exact-native lane repeats netlist and ERC exports on digest-pinned KiCad
10.0.0 and 10.0.5 images. It checks the selected version, pin functions, exact
net assignments, stable normalized netlist evidence, and zero ERC errors. The
schematics demonstrate source-to-netlist compatibility for these synthetic
inputs; they do not establish field precision or an electrical requirement.
