# Synthetic STM32 CubeMX pin-map fixture

`valid.ioc` is an authored test input for the source-bound firmware-to-schematic
pin-map comparison. Its MCU identity, signals, labels, and package pins are
invented for this repository; it contains no product design data.

The fixture covers three explicitly mapped signals and one reasoned SWD pin
exclusion. Tests derive faults by changing a signal, label, net assignment,
component identity, pin inventory, or IOC assignment. The matching input is
the valid control. Unsupported keys, duplicate field assignments, and
conflicting alternate-function suffixes that identify the same physical pin
are separate parser-coverage faults.
Reordering valid assignment lines preserves the mapped result but changes the
source hash, so this metamorphic control checks semantics and provenance
independently.

The native netlist side is built from synthetic `NetlistContract` records in
`tests/test_stm32_pin_map.py`. Source-receipt and CLI/MCP parity cases use the
same synthetic project inputs.
