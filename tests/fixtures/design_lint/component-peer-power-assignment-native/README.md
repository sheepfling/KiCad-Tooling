# Synthetic peer power-pin assignment fixtures

These source-hashed schematics test the cross-symbol `PART_ID` comparison in
`component.peer_power_pin_assignment_divergence`. Each fixture contains two
fitted synthetic module symbols with distinct native symbol IDs but the same
`PART_ID`, value, footprint, complete pin inventory, pin functions, and
electrical types. Pin 1 is named `VDD`; pin 2 is named `GND`. Both pins use
native `power_in` type.

| Fixture             | U1 assignments                                       | U2 assignments                                       | Expected lint result                                                                  |
| ------------------- | ---------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `fault.kicad_sch`   | `VDD` → `SYNTHETIC_NET_A`; `GND` → `SYNTHETIC_NET_C` | `VDD` → `SYNTHETIC_NET_B`; `GND` → `SYNTHETIC_NET_D` | `REVIEW`: LINT-070 supply/return findings and independent LINT-046 reviews on A and B |
| `control.kicad_sch` | `VDD` → `SYNTHETIC_NET_1`; `GND` → `SYNTHETIC_NET_2` | Same two net assignments as U1                       | `REVIEW`: LINT-070 is quiet; independent LINT-046 review remains on net 1             |

The control confirms LINT-070 stays quiet when corresponding assignments
match. Both reports remain `REVIEW` because these minimal power-input fixtures
have no fitted decoupling capacitor; the native lane checks that independent
LINT-046 evidence on the expected synthetic supply net or nets. The fault asks
a reviewer to check the split; it does not assert that matching component
identities require common nets. Separate supplies and return domains may be
intentional. This lint does not merge nets or prove PCB copper, off-board
connections, part interchangeability, or electrical approval.

The native acceptance lane exports both fixtures twice with the catalogued
KiCad 10.0.0 and 10.0.5 images. It checks symbol IDs, `PART_ID`, value,
footprint, pin inventories, function and electrical-type metadata, exact pin
assignments, findings, and repeatability of normalized netlist evidence. No
product schematic or project expectation is used.

SHA-256 source digests:

- `control.kicad_sch`: `23fec400e1e0a0581abc650a7d108512948d5d0b14744a276ebabc75a94be67d`
- `fault.kicad_sch`: `2e4bc0c9f883e948660b1982a7ccae888c18c3b52b9ae285b878666a7353c4c6`
