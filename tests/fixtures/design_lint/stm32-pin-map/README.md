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

The cohort comparison adds three standalone, repository-authored parser inputs:

- `suffix-conflict-forward.ioc` and `suffix-conflict-reversed.ioc` contain the
  same conflicting PA13 alternate-function assignments in opposite orders.
  Their SHA-256 values are `05fe584b6e33cff15f18dc61f107ef38f736298ce595da38983a70b7235233b2`
  and `e7afc69ae58e7103afb4833ffdc41d44c4de21a4510a2792ebd8b9ad1d8d806a`.
- `escaped-pin-key.ioc` contains a CubeMX escaped-space key for PH0. Its
  SHA-256 is `e5117e0d1d63089e31e97fc1c653cffa341bd3da82bfe7ac7a5fd7c95e8316ca`.

These inputs support the source-pinned STM32 parser comparison recorded in
[`cohort-stm32-pin-checker`](../cohort-stm32-pin-checker/README.md). They are
invented for tooling regression tests and do not represent a product project.
