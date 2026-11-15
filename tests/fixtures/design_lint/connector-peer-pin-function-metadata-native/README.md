# Connector peer pin-function metadata fixtures

These tooling-owned schematic fixtures are derived from the repository's
synthetic matched connector fixture. They contain two distinct native
connector symbols with the same value, footprint, `PART_ID`, complete two-pin
inventory, electrical types, and assignments. The generic fault changes J1
pin 2's library pin name from `UART_RX` to the generic `Pin_2`; the missing
function fault leaves J1 pin 2's library pin name blank. J2 keeps `UART_RX` in
both faults. Pin 1 remains the common function and net anchor. The control
keeps both pin-2 names at `UART_RX`. The anchor pin is named `GND` in both
symbols.

The review prompt identifies an asymmetry in authored symbol metadata. It does
not establish the approved part pinout, decide which function is correct,
require a connection, or prove PCB copper continuity. The fixtures contain no
cohort board, customer source, or proprietary project data. Repeated native
exports run against digest-pinned KiCad 10.0.0 and 10.0.5 Docker images.

SHA-256 source digests:

- `generic-function-peer-fault.kicad_sch`:
  `56118298a9cd7a567bfb4df115cf0b6f5fe7c64a3de2ad4984b28f3c10d2152e`
- `missing-function-peer-fault.kicad_sch`:
  `d244a846990c8d99fd0ae8219c9eab3900c37de58b91dd01f785f0adac755e22`
- `metadata-matched-control.kicad_sch`:
  `389c91306af19802373ee42ef5aebc8064e4a8e21b9c7758e916e658239a6469`
