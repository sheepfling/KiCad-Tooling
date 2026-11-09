# I2S clock/frame same-net fixtures

These tooling-owned schematics exercise `bus.i2s_clock_frame_same_net` using
an embedded synthetic four-pin audio IC symbol. They contain no product board,
connector pinout, or project expectation.

| Fixture | Native assignment | Expected result | SHA-256 |
| --- | --- | --- | --- |
| `fault.kicad_sch` | U1.1 `I2S_BCLK` and U1.2 `I2S_LRCLK` share `I2S_SHARED` | One default-REVIEW prompt | `80dd97e68045c32d750d41108aa3fcb67f21756a9c3a44aedd5772007c2d6cb9` |
| `control.kicad_sch` | Bit clock and word select use separate nets | No finding | `296e48767b563dfbb8f71e4bde45353c26480fff69293fa8a0e939f13a046ed4` |

The exact-native lane repeats netlist and ERC exports on digest-pinned KiCad
10.0.0 and 10.0.5 images. It checks the selected version, pin functions, exact
net assignments, stable normalized netlist evidence, and zero ERC errors. The
schematics demonstrate source-to-netlist compatibility for these synthetic
inputs; they do not establish field precision or an electrical requirement.
