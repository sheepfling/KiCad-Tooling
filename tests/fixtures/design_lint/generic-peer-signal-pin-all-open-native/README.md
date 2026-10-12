# Synthetic all-open generic connector signal peers

These tooling-owned schematics exercise the opt-in
`connector.generic_peer_pin_all_open` review for a generic native `input` pin.
Two fitted instances have the same complete two-pin inventory. Pin 1 carries
the same `+5V` net on both connectors; generic `Pin_2` is unassigned in the
fault and connected to `GND` in the control.

The native lane exports both schematics twice on digest-pinned KiCad 10.0.0
and 10.0.5 images. It checks that the netlist retains native pin type
`input`, generic function `Pin_2`, the shared anchor, and the all-open
fault/control distinction. The signal type narrows a comparison group; it
does not identify the interface function or establish a required connection.
The rule remains default-off.

| Fixture             | Pin 1             | Pin 2                     | Expected result               |
| ------------------- | ----------------- | ------------------------- | ----------------------------- |
| `fault.kicad_sch`   | J1/J2 share `+5V` | J1.2/J2.2 unassigned      | `REVIEW` from the opt-in rule |
| `control.kicad_sch` | J1/J2 share `+5V` | J1.2/J2.2 share `GND`     | `PASS`                        |

## Source hashes

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `77adf18dff325f85bf7675d42a25ad1603aa6debb67a96b586646598fac75d37` |
| `control.kicad_sch` | `144e3e571c2023e4d90048c95fe16f532bcd459c3f5a6e6da6c8b2632282046b` |

Receipts stay under ignored `build/ci/` directories.
