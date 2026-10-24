# CAN signal assigned to a named rail

These are Tooling-authored schematic fixtures containing one synthetic CAN
controller. They are not derived from a product design.

| Case                | SHA-256                                                            | Expected result                                                 |
| ------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------- |
| `fault.kicad_sch`   | `8780151a3e20f7ae3d784870cf5eb146c9ab2816f21a561a72e15bd59e9e284a` | `U1.1` function `CAN1_TX` is assigned to `GND`; emit REVIEW.    |
| `control.kicad_sch` | `f443a372c06d1862c7250d3797269fd29ced89d0a8def43c184d8762c00a865e` | `CAN1_TX` stays on a neutral signal net; no named-rail finding. |

The digest-pinned native lane exports each source twice with KiCad 10.0.0 and
10.0.5, checks the normalized netlist hashes repeat, and requires clean ERC.
The check is a review clue based on pin-function and net-label names; it does
not determine CAN mode, electrical potential, transceiver behavior, or PCB
continuity. Intentional straps remain valid project decisions.
