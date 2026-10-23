# Synthetic regulator-feedback source fixtures

These tooling-owned schematics contain one simplified eight-pin adjustable
regulator and two mapped resistors. Pin functions, symbol identity, footprint
identity, values, and named nets are embedded in each source. The map used by
the regression is an explicit synthetic project requirement.

| Source                           | Feedback topology                          | Expected result                   |
| -------------------------------- | ------------------------------------------ | --------------------------------- |
| `control.kicad_sch`              | 180 kΩ / 33 kΩ divider from REG_OUT to GND | Complete coverage; no finding     |
| `value-fault.kicad_sch`          | Upper resistor is 220 kΩ                   | Output interval merits review     |
| `split-feedback-fault.kicad_sch` | Lower resistor feedback pin is on `FB2`    | Split feedback node merits review |

The acceptance lane exports native netlists and ERC reports twice using
digest-pinned KiCad 10.0.0 and 10.0.5. It checks exact source hashes, normalized
repeatability, mapped component identity, pin inventory and function, net
membership, nominal resistance, calculated output interval, and zero ERC
errors. These fixtures test the source-bound contract adapter; they do not
validate a real regulator, datasheet, compensation network, stability, or PCB
routing.
