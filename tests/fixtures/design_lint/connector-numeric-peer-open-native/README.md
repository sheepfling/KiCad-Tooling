# Numeric-only connector peer fixtures

These synthetic schematics adapt tooling-owned two-peer connector fixtures so
pin 1 has the numeric-only native function `1`. The exact-symbol cases share
pin 2 on `GND`. The PART_ID cases use two embedded symbol aliases with the same
nonempty PART_ID, value, footprint, complete pin inventory, and pin metadata.

| Fixture                          | Numeric target assignment                  | Expected result                                                        |
| -------------------------------- | ------------------------------------------ | ---------------------------------------------------------------------- |
| `fault.kicad_sch`                | J1.1=`+5V`; J2.1=open                      | `REVIEW` for `connector.generic_peer_pin_open_outlier`                 |
| `control.kicad_sch`              | J1.1/J2.1=`+5V`                            | No numeric peer-open finding                                           |
| `no-connect-ambiguity.kicad_sch` | J1.1=`+5V`; J2.1=explicit KiCad no-connect | `REVIEW`; netlist evidence cannot distinguish it from an unmarked open |
| `part-id-fault.kicad_sch`        | J1.1/J2.1=`+5V`; J3.1=open                 | `REVIEW` across two native symbol aliases with the same PART_ID        |
| `part-id-control.kicad_sch`      | J1.1/J2.1/J3.1=`+5V`                       | No numeric peer-open finding                                           |

The numeric function and shared anchor do not identify a required net. The
fault is a review prompt only. KiCad's native netlist normalizes explicitly
no-connected and otherwise open pins to the same unconnected representation,
so the no-connect case documents a known false-positive boundary. A
source-matched pin map or an exact reviewed ignore can suppress an intentional
open. These fixtures are tooling-owned test inputs; they are not copied from a
product board and are not for manufacture.

## Source hashes

| Source                           | SHA-256                                                            |
| -------------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`                | `fecaec12fc64b0cbc9bbe8c90a0a604868782128b2ae206b71f52ad3e8d3496d` |
| `control.kicad_sch`              | `9db45f6376dc7c10e7dea042a3912ab4afca4ae3e7554b10a6ab847dd96701eb` |
| `no-connect-ambiguity.kicad_sch` | `2abc2eb0203e003e91fb42e1be6a9975a53d1387fc26752ed16c232ac4757847` |
| `part-id-fault.kicad_sch`        | `ad5df0aaf379b4db0386be2ed632c4c197b39c68db75d0028f05dc0b4c68387f` |
| `part-id-control.kicad_sch`      | `329fdda52919463f4a3788f27353ae3510e51aaa48dcba93f3ac1dcc7d010115` |
