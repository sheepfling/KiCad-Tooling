# BJT base/collector same-net native fixture

This tooling-owned synthetic schematic exercises the default-off
`component.bjt_base_collector_same_net` review. It contains NPN and PNP examples
whose native base and collector pins share a schematic net. Such a tie can be
an intentional diode-connected transistor, so the finding is a review prompt,
not a declaration that the circuit is defective. No product project or source
is included.

| Case          | Source                                                                                             | Expected result                                                                |
| ------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Fault fixture | `fault.kicad_sch`                                                                                  | Q1 NPN and Q2 PNP each produce one candidate when review is enabled            |
| Control       | [`../bjt-terminal-order-native/control.kicad_sch`](../bjt-terminal-order-native/control.kicad_sch) | Both supported BJTs have distinct base and collector assignments; no candidate |

The fault source SHA-256 is
`32dff25a342646150e18a765bcba4cc13ef360d52d06b51ef448bad4c5f17a21`.
The shared control source SHA-256 is
`2b68e0bb4818e82917047e2e9caf07b0b9ebf25cf5fd939a6bb4b7a1f7c45845`.

The digest-pinned native lane repeats KiCad 10.0.0 and 10.0.5 netlist and ERC
exports, checks for zero ERC errors, and compares normalized evidence. Native
exports validate fixture interpretation only; they do not establish device
behavior, physical pin mapping, or PCB copper continuity.
