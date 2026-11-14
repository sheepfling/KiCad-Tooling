# Connector peer pin-function fixtures

These tooling-owned native schematics contain two synthetic connector symbols
with matching value, footprint, nonempty `PART_ID`, complete pin inventory,
electrical types, and assigned nets. The fault changes only J2 pin 2's native
function from `UART_RX` to `UART_TX`. Pin 1 remains a common function and net
anchor. The control gives both pin-2 symbols the same function.

The finding is a configurable review cue about inconsistent symbol metadata.
Matching project metadata and net assignments do not prove the symbols refer
to the same approved part, select the correct function, or establish PCB copper
continuity. The native exports are repeated on digest-pinned KiCad 10.0.0 and
10.0.5 images.

The separate `pin-inventory-disagreement-fault.kicad_sch` fixture adds one
named `VBUS`/`power_in` pin to J2's native symbol inventory and assigns it to
`SYNTHETIC_NET_3`, while J1 retains the matching two-pin inventory. It reuses
the matched two-pin fixture below as the valid control. The review requires
complete metadata on the common pins and one shared-net anchor; it does not
claim the added pin is incorrect or require its net to be common.

SHA-256 source digests:

- `pin-function-disagreement-fault.kicad_sch`:
  `9c99eec630de015d77bf04fbc0ef024749e4f663cd6df4193dce344384550699`
- `pin-function-matched-control.kicad_sch`:
  `01d44e2b8f5a5a41fc830f8eea20161c6fc363075f62c8b0cc35bc6cbbf5f335`
- `pin-inventory-disagreement-fault.kicad_sch`:
  `b50a7d3c49ff20220e613373c15e0ebf68ad5eabe7bfc428d83647720743c25f`
