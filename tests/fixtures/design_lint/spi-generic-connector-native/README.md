# Generic SPI connector review fixtures

These are synthetic tooling regressions. They contain no external board or
project data.

`fault.kicad_sch` assigns generic connector contacts J1.1–J1.3 to the exact
SPI_SCK, SPI_MOSI, and SPI_MISO nets of fitted U1's native clock and data
functions. The connector also has an AUX contact on a separate net and an open
VCC contact. The heuristic should request pinout review and include both
contacts as native evidence. `control.kicad_sch` assigns explicit SCK/MOSI/MISO
connector functions to those same nets; the generic-pin heuristic should stay
quiet while the open VCC remains visible in the schematic source. Neither case
defines whether VCC or a return must be connected.

The digest-pinned KiCad 10.0.0 and 10.0.5 lane exports each source twice, then
compares normalized netlists and lint findings. Source hashes are registered in
`kicad_tooling/ci_hosted_spi_generic_connector_cases.py`.

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `713ff06b7497f9f57287324ca916c567243580e46e6c60239bf28049c865dda7` |
| `control.kicad_sch` | `030cffc1bd67e6b3eaf925e02009b52db2a2382eba4d7ab548bb13543296d8f7` |
