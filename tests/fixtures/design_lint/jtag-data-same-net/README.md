# JTAG TDI/TDO same-net fixtures

These tooling-authored schematics contain one synthetic fitted IC and test the
review-only same-net heuristic. They do not describe a product board.

- `fault.kicad_sch`
  - Result: U1 pins 3 (TDI) and 4 (TDO) share `JTAG_DATA_SHARED`; one REVIEW prompt.
  - SHA-256: `50b3259121e4ac74c2db976d3f0ed3adf680969cccb5025ab89343293e1ecbbf`.
- `control.kicad_sch`
  - Result: U1 pins 3 (TDI) and 4 (TDO) have separate nets; no prompt.
  - SHA-256: `4ff3cf87d3c41385495317d0a7bb29fa568701568fa068722339779ca276e83c`.

The digest-pinned native lane checks exact pin functions and net assignments,
then repeats netlist and ERC exports on KiCad 10.0.0 and 10.0.5. The fixtures
must have no ERC errors and repeat-identical normalized netlists. This evidence
validates native export and the bounded schematic predicate; it does not prove
whether the loopback is electrically intended or inspect PCB copper.
