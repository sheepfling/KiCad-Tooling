# I2S data-output sharing fixtures

These tooling-owned synthetic schematics exercise `bus.i2s_data_outputs_share_net` with two complete
fitted audio-codec symbols. Passive native pins keep the review candidate independent of ERC
output-conflict reporting.

| Fixture             | Native assignment                                                                           | Expected candidate                  | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | U1.3 and U2.3 `SDOUT` share `I2S_DATA_SHARED`; their I2S clocks and frame pins are assigned | One off-by-default review candidate | `a18aa0c56446bfa35874c1aa1e555d2a5f152522bb36d1eab552c291ef4e9f73` |
| `control.kicad_sch` | The two `SDOUT` pins use separate nets; clock and frame pins are shared                     | No candidate                        | `0f05fe6c579a4b8950bb9e932f77baacd28046a9f2bb3eef607e1482d5c16528` |

The digest-pinned KiCad 10.0.0 and 10.0.5 native lane repeats netlist and ERC exports. It checks
exact data-pin functions and assignments, stable normalized netlists, and zero ERC errors. These
fixtures do not establish that I2S outputs must be isolated: tri-state or time-division audio
topologies may intentionally share data lines.
