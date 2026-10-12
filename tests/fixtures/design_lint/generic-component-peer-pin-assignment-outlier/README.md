# Generic component peer pin assignment outlier fixtures

These tooling-owned schematic fixtures test the default-off rule
`component.generic_peer_pin_assignment_outlier`.

| Fixture             | Native assignments                                                       |
| ------------------- | ------------------------------------------------------------------------ |
| `fault.kicad_sch`   | U1.1 and U2.1 use `+5V`; U3.1 uses `+3V3`; all pin 2 contacts use `GND`. |
| `control.kicad_sch` | U1.1, U2.1, and U3.1 all use `+5V`; all pin 2 contacts use `GND`.        |

All three fitted U instances use one exact synthetic symbol with a generic
`Pin_1` function and two passive pins. The fault has a strict two-peer majority
on pin 1; the control assigns it consistently. The shared GND pin supplies
comparison context only. Neither fixture states that pin 1 must use the
majority net or that any two domains must be joined.

Both sources are marked `NOT FOR MANUFACTURE`. The native fixture lane exports
each file twice with digest-pinned KiCad 10.0.0 and 10.0.5, then checks the
target finding and normalized netlist repeatability. It does not run ERC/DRC,
establish PCB continuity, or measure physical component behavior.

## Source hashes

| Source             | SHA-256                                                            |
| ------------------ | ------------------------------------------------------------------ |
| `fault.kicad_sch`  | `2235639e107cfe4b060c052069c5c2bbc2a48dbef40c2bb22c8219ad6f19e7ba` |
| `control.kicad_sch`| `22f1efb0f7df6458d4523c79bc6b1e5cdd31b57463b8072cd4002105106179dc` |
