# CAN module TXD/RXD pins assigned to named rails

These Tooling-authored schematic fixtures contain a synthetic controller and a
connector explicitly named as a CAN transceiver module. They are not derived
from a product design.

| Case                | SHA-256                                                            | Expected result                                                                   |
| ------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| `fault.kicad_sch`   | `ac85d23bf274c93411a8960c81b7abeee3d8df3c4438b5a992431e4b7d229532` | `J1.1 TXD` is on `GND` and `J1.2 RXD` is on `+3V3`; emit two REVIEW candidates.   |
| `control.kicad_sch` | `36851f1d1b838183e758a734e65565c89994a075574784b3280e028b27080a4c` | The identified module's TXD/RXD pins use neutral signal nets; emit no candidates. |

The digest-pinned native lane exports each fixture twice with KiCad 10.0.0 and
10.0.5, checks repeatable normalized netlists, and requires clean ERC. The
identity text, native pin functions, complete pin inventory, and one net
assignment per finding are all required evidence. Ordinary serial connectors
with generic TXD/RXD functions are valid quiet controls in the synthetic unit
suite. The result is a configurable review clue; it does not determine module
contents, electrical potential, intended wiring, PCB copper, or continuity.
