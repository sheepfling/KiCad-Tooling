# USB-C SBU same-net fixtures

These tooling-authored schematics exercise the review heuristic for a fitted
synthetic USB-C controller whose SBU1 and SBU2 functions share one schematic
net. They contain no product design or supplier reference design.

- `fault.kicad_sch` assigns J1.1, J1.2, U1.1, and U1.2 to `SBU_SHARED`.
- `control.kicad_sch` assigns SBU1 and SBU2 to separate nets.

SHA-256 digests:

- fault: `c4b68ed7849e661f3a5fe3eaf901947b7c83eda649b00ffce93fa3c4bdc534c6`
- control: `255e96c70b634c5658fd35d05722f0098d838478bf07d4e15744c15e48c4f8f9`

The same-net assignment is a synthetic review case, not an assertion that all
USB-C implementations require separate SBU lines. Native exports are repeated
with the digest-pinned KiCad 10.0.0 and 10.0.5 images.
