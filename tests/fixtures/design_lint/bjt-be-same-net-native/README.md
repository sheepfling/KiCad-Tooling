# BJT base/emitter same-net native fixture

This tooling-owned synthetic schematic exercises the default-off
`component.bjt_base_emitter_same_net` review. It is made from the repository's
synthetic transistor fixture and contains no product board source.

| Case    | Source                                                                                             | Expected result                                                                                                             |
| ------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Fault   | `fault.kicad_sch`                                                                                  | NPN Q1 and PNP Q2 each have their native base and emitter assigned to one schematic net; two review candidates when enabled |
| Control | [`../bjt-terminal-order-native/control.kicad_sch`](../bjt-terminal-order-native/control.kicad_sch) | Both base and emitter assignments are distinct; no finding                                                                  |

The fault source SHA-256 is
`3ff07964aaea5f8a879d82eaf918902c8b5a1ff83dee877a8609613a6c91b77b`.
The shared control source SHA-256 is
`2b68e0bb4818e82917047e2e9caf07b0b9ebf25cf5fd939a6bb4b7a1f7c45845`.

The digest-pinned native lane repeats KiCad 10.0.0 and 10.0.5 netlist and ERC
exports. A base/emitter assignment to one schematic net can intentionally hold
a transistor off. The prompt does not infer intended operation, physical pin
mapping, PCB copper, or device behavior.
