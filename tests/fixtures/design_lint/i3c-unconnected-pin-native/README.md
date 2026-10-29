# I3C one-sided open pin fixtures

These public tooling-owned synthetic schematics contain one two-pin I3C
controller with explicit `I3C1_SDA` and `I3C1_SCL` functions. The control
assigns both pins to separate neutral-named nets. The fault assigns SDA to
`I3C_SDA` and marks SCL explicitly unconnected. The fixture lane repeats
netlist and ERC exports with digest-pinned KiCad 10.0.0 and 10.0.5.

| Case    | Source              | SHA-256                                                            |
| ------- | ------------------- | ------------------------------------------------------------------ |
| Fault   | `fault.kicad_sch`   | `6c97dd20de08edc4bd6f0a5a23529faa15296632f4cdb8ad983399bc888f9fd3` |
| Control | `control.kicad_sch` | `2e6219d860a33e9ccd54078d86b7c4afd50f3b5955da6750ba9ca4f6519768c3` |

The native check verifies pin functions, assignments, no-connect evidence,
zero ERC errors, repeatable exports, and the expected REVIEW candidate. It
does not establish interface use, required connectivity, routed copper, or
physical continuity. All inputs are synthetic; no project source or external
expectation is included.
