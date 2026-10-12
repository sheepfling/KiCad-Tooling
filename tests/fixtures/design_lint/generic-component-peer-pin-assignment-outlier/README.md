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
| `fault.kicad_sch`  | `ebf8109ce0270fbee3ed525d3e20aaf2b9c06dab845abc8fd29c828948428dce` |
| `control.kicad_sch`| `b8a2b2d9969f779a12dd0ec5e4608895a49205b74f51e407db627bc99004f18a` |
