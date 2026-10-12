# USB SuperSpeed peer-reference native fixtures

These source schematics are synthetic tooling fixtures. Their connector and PHY
pin numbers are fixture-local metadata, not a production connector pinout.

`fault.kicad_sch` contains direct TX-to-RX and RX-to-TX P/N paths. The connector
return is `USB_GND` and the PHY return is `PHY_GND`, so both paths should prompt
for review. `control.kicad_sch` keeps the same data topology and puts both
explicit return pins on `BOARD_GND`, so neither path should prompt.

The native lane exports each source twice with the exact digest-pinned KiCad
version selected by the public template checkout. It verifies the pair pin
functions, exact two-pin net membership, finding families, and repeatability.

| Case    | SHA-256                                                            |
| ------- | ------------------------------------------------------------------ |
| fault   | `4eab8226ec5b526a16c880453f54202bb3df9b42b444bd82684d92fd7720c095` |
| control | `5b8bd68163f9493c91c643b55d283f9514522ccc67b2cc7e37955e83e0b7b400` |

The hosted `v0.5.0rc194` gate (GitHub Actions run `38309295549`) passed this
fault/control lane on digest-pinned KiCad 10.0.0 and 10.0.5. Both complementary
data directions reported separate-reference paths in the fault; the common
reference control stayed quiet, and repeated normalized netlists matched.
