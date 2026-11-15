# JTAG signal named-rail fixtures

These tooling-owned schematics exercise `bus.jtag_signal_on_named_rail` with a
synthetic four-pin debug target. The fault places TCK on `GND` and TDI on
`+3V3`; the control assigns all four signals to neutral names.

| Fixture             | Native assignment                      | Expected result            | SHA-256                                                            |
| ------------------- | -------------------------------------- | -------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | U1.1 TCK on `GND`; U1.3 TDI on `+3V3`  | Two default-review prompts | `78d7c9e9544b6af932e1f3283bd83c8d300f8266bc6dd844b59702ebfb382ad2` |
| `control.kicad_sch` | TCK, TMS, TDI, and TDO on neutral nets | No finding                 | `27d17fb821a66b12fe794a13c417edc4873b1ade32afeb187d877d135cfcb8ba` |

The exact-native lane repeats netlist and ERC exports on digest-pinned KiCad
10.0.0 and 10.0.5 images. It checks version, pin functions, assignments,
repeatability, and zero ERC errors. These synthetic schematics establish
source-to-netlist compatibility only; they do not prove JTAG use, pinout
intent, electrical potential, or a required board connection.
