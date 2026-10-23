# BJT collector/emitter same-net native fixtures

These tooling-owned synthetic KiCad schematics exercise
`component.bjt_collector_emitter_same_net`. They contain no board project or
product source.

| Case    | Source                                                                                             | Expected rule result                                                                                                 |
| ------- | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Fault   | `fault.kicad_sch`                                                                                  | Q1 NPN collector/emitter share `NPN_CE`; Q2 PNP collector/emitter share `PNP_CE`; two review candidates when enabled |
| Control | [`../bjt-terminal-order-native/control.kicad_sch`](../bjt-terminal-order-native/control.kicad_sch) | Both fitted BJT collector/emitter pairs have distinct native net assignments; no same-net candidate                  |

The fault source SHA-256 is
`5fda7f1f6b248be52260d4e472444f9a517ba5b92bec06bc2f5ef3609cdf93c3`.
The shared control source SHA-256 is
`2b68e0bb4818e82917047e2e9caf07b0b9ebf25cf5fd939a6bb4b7a1f7c45845`.

The digest-pinned native lane exports each source twice on KiCad 10.0.0 and
10.0.5, checks for zero ERC errors, and compares normalized netlist, ERC, and
lint results. The review is default-off and does not establish intended circuit
behavior or PCB copper continuity.
