# Switching-regulator loop-map fixture

`unmapped.kicad_sch` is a tooling-owned synthetic four-pin symbol under the
KiCad `Regulator_Switching` library prefix. Its fitted U1 has complete native
pin-function and electrical-type metadata, and separate exact net assignments
for `SW` and `LX1`. The native regression exports it with digest-pinned KiCad
10.0.0 and 10.0.5, parses the export, checks a review candidate when no map
covers those pads, and checks quiet behavior when both are mapped.

This file is an isolated synthetic schematic fixture. It contains no user,
cohort, or proprietary board source and makes no assertion about a physical
switching regulator, loop geometry, return path, or electrical limit.

Pinned source hash:

- `unmapped.kicad_sch`: `48f279e9a59754ab1c414138f8dafab15e8c933a5ac953a3faf845c7fb51d7cf`
- `netlist.xml`: `e1c4969123837d1ae59b790eb4373071a3a8008311bf2b0664ed7429e476111d`

The compact XML file is a synthetic parser input for CLI/MCP parity; the native
test exports its netlists from `unmapped.kicad_sch` inside each pinned KiCad
image.
