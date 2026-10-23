# Synthetic BJT base-bias fixtures

These tooling-owned schematics exercise a bounded review heuristic for exact
basic NPN and PNP symbols. They contain no external project design data.

| Source              | Base drive                                                    | Base-emitter resistor                                         | Expected result                                         |
| ------------------- | ------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------- |
| `fault.kicad_sch`   | Each BJT base is driven through a fitted 1 kΩ series resistor | None                                                          | Review both bases for a potentially undefined off-state |
| `control.kicad_sch` | Same series-driven topology                                   | A fitted 100 kΩ resistor directly spans each base and emitter | No base-bias review                                     |

The fixtures are exported twice with digest-pinned KiCad 10.0.0 and 10.0.5;
the native netlist, ERC results, and findings must repeat. The review rule is
opt-in because push-pull drive, internal bias, and other topologies can make
an external base-emitter resistor unnecessary. The check does not decide
whether a resistor is required or adequate, and it does not establish PCB or
physical behavior.

Source SHA-256:

- `fault.kicad_sch`: `55cc042c83a59be9df77953cb9167533fe459bf5a7e5b7b6d2bcf3e6cc8d4d17`
- `control.kicad_sch`: `e457df2782144a90b2c74141892defe416b82e5c0c10d5546d9ab6c854155461`
