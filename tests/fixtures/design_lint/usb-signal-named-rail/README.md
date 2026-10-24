# USB data pin assigned to a named rail

These Tooling-authored synthetic schematics exercise
`bus.usb_signal_on_named_rail`. The control connects the bidirectional USB 2.0
data pins through neutral `USB_D+` and `USB_D-` nets. The fault keeps U1.1's
native `USB_DP` function but assigns it to a `GND` net label.

- `control.kicad_sch`
  (`30270e674ad045a2ebc238b6f632ed455c04f549d6c53061f74151c77d160002`): no named-rail review.
- `fault.kicad_sch`
  (`9330de44f6600afd92d2aa7199eced1ca6e892ed74fb5765f20a1832eef97148`): review
  `U1.1: USB_DP on return-like net GND`.

The native fixture lane repeats netlist and ERC exports with digest-pinned
KiCad 10.0.0 and 10.0.5 images. The aliases for USB SuperSpeed and numbered
USB2 ports are covered by synthetic regressions; the native schematics here
exercise the unnumbered USB2 D+/D- case.

This heuristic recognizes bounded pin-function and net-label clues. It does
not establish electrical potential, USB topology, routed copper, or physical
continuity, and intentional direct rail assignments remain project decisions.
