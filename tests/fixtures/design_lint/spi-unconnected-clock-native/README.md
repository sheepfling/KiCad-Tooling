# SPI open-clock fault and control

These synthetic KiCad schematics are tooling-owned fixtures. The fault has an
explicit SCK pin with a no-connect marker while MOSI remains assigned. The
control assigns both pins. They contain no project or cohort board source.

| Case    | Source              | SHA-256                                                            |
| ------- | ------------------- | ------------------------------------------------------------------ |
| Control | `control.kicad_sch` | `cf9cf52926767b8d4a3ba311bec79f669d95a2d3fc4865cdc895ab7b48c9e738` |
| Fault   | `fault.kicad_sch`   | `bd2d07d875ef4b580a8d378dfc92d757c4a856b4ce76b5f2167810184fe0f214` |

The focused native lane exports netlists and ERC reports repeatedly on digest-
pinned KiCad 10.0.0 and 10.0.5. It verifies that only U1.1 (SCK) is open and
that the default-off lint emits `U1.1: SCK` only when explicitly enabled. This
checks recognition and evidence handling; it does not prove the clock is
required, firmware use, PCB copper continuity, or electrical approval.
