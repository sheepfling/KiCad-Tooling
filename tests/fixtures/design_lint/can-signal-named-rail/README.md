# CAN signal assigned to a named rail

These are Tooling-authored schematic fixtures containing a synthetic CAN
controller and connector. They are not derived from a product design.

| Case                | SHA-256                                                            | Expected result                                                         |
| ------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| `fault.kicad_sch`   | `bd3ab9e52d76f8a0befdc186c3e61d56faf8ea46b066cd0be5fc8703a436cc6c` | `U1.1` and `J1.1` CAN TX functions share `GND`; emit REVIEW for both.   |
| `control.kicad_sch` | `d3c57cce862e757ba2473486fdbcfd88f2faf9cb583f1b9a9ea897a53b36fb86` | IC and connector TX use neutral signal nets; `J1.2` remains on `GND_B`. |

The digest-pinned native lane exports each source twice with KiCad 10.0.0 and
10.0.5, checks the normalized netlist hashes repeat, and requires clean ERC.
The check is a review clue based on pin-function and net-label names; it does
not determine CAN mode, electrical potential, transceiver behavior, or PCB
continuity. Intentional straps remain valid project decisions.
