# Synthetic SPI data input/output same-net fixtures

These authored fixtures contain one fitted synthetic IC with native `COPI`
(input) and `CIPO` (tri-state output) pins. `fault.kicad_sch` assigns both to
`SPI_DATA`; `control.kicad_sch` keeps the data nets separate. Both are marked
not for manufacture and contain no external project or cohort source. The
control includes a synthetic controller MOSI output to drive the peripheral
COPI input, so native ERC can check a complete fault/control pair.

The default-off lint asks for review because loopback, single-wire modes, or
part-specific behavior can intentionally join these functions. It does not
assert that the pins must remain separate.

The exact-version native lane repeats netlist and ERC exports under digest-pinned
KiCad 10.0.0 and 10.0.5, confirms the native assignments and review candidate,
and requires no ERC errors for either case.
