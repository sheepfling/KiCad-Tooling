# Synthetic multi-bus contract parity fixture

This native XML netlist is tooling-owned synthetic data. It combines I2C, CAN,
USB-C, and SPI assignments so one saved electrical view exercises their
authored contract checks together. It is not copied from a board or project
repository.

The parity regression uses this baseline for its passing report. Its fault
control changes selected component values and moves one SPI chip-select pin to
a different net; the expected contracts remain independently specified in the
test.
