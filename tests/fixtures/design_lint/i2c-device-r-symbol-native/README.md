# Synthetic I2C resistor symbol identity fixture

`symbol_resistor.kicad_sch` contains one two-pin `Device:R` symbol under the
nonstandard reference `X1`, connected from `I2C_SDA` to `+3V3`. Its SHA-256 is
`1793291946117b88171d407379c6e768fb10e8b26feae7736f2206c57e5806b4`.

The exact-version native lane checks that KiCad exports `Device:R`, pins 1 and
2, the 4.7 kΩ value, and both net assignments, then verifies that the bounded
I2C resistor-path analyzer recognizes `X1` as a local pull-up. The fixture is
synthetic and tests schematic netlist evidence only; it does not establish
component identity beyond the symbol ID, PCB connectivity, resistor behavior,
or electrical suitability.
