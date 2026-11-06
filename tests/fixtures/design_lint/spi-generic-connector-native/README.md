# Generic SPI connector review fixtures

These are synthetic tooling regressions. They contain no external board or
project data.

`fault.kicad_sch` assigns generic connector contacts J1.1–J1.3 to the exact
SPI_SCK, SPI_MOSI, and SPI_MISO nets of fitted U1's native clock and data
functions. The heuristic should request pinout review. `control.kicad_sch`
assigns explicit SCK/MOSI/MISO connector functions to those same nets; the
generic-pin heuristic should stay quiet. Both fixtures include separate ground
and supply nets to show that this lint does not define their relationship.

The digest-pinned KiCad 10.0.0 and 10.0.5 lane exports each source twice, then
compares normalized netlists and lint findings. Source hashes are registered in
`kicad_tooling/ci_hosted_spi_generic_connector_cases.py`.

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `9b5eabbcc50ab7e9b19557d438e917f64ffb81ecdf3bdb151ea8087ffa53e538` |
| `control.kicad_sch` | `e11144f442f5d727753a010bc3bb22fb2cfcc2662efa263ea1e291f90f51699a` |
