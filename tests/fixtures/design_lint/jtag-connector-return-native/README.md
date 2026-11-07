# JTAG connector return-role fault

This tooling-owned synthetic schematic retains a `GND` net label while changing
connector pin 5's native function to generic `Pin_5`. Pins 1 and 2 remain
generic contacts on the native U1 TMS and TCK nets. It tests the distinction
between a net name and an independently reviewed connector return role.

- **Fault:** [`fault.kicad_sch`](fault.kicad_sch), SHA-256
  `9cb38f8584ab580cb907ba588d576c3f6426fe2310a85d4aa238098e6659afdb`.
  Expect one review prompt for J1's generic TCK/TMS pair without an identified
  return.
- **Control:** [explicit-GND JTAG control][jtag-control], SHA-256
  `814bef2ba33b6886936e3c7536c61b09f89d806a62c23c47a18065e7826461c7`.
  Its explicit native `GND` connector function suppresses the return-role
  prompt.

Each source is exported twice with digest-pinned KiCad 10.0.0 and 10.0.5
images. This is a heuristic review cue: it does not require board ground on
every JTAG connector, infer external wiring, or prove PCB copper continuity.

[jtag-control]: ../jtag-generic-connector-native/fault.kicad_sch
