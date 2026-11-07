# USB SuperSpeed two-pin connector return fixtures

These sources are synthetic tooling fixtures. The connector and PHY pin
numbers are fixture-local and are not an approved production pinout.

`fault.kicad_sch` connects a two-pin connector to one exact PHY SuperSpeed RX
pair and has no connector return contact. `control.kicad_sch` adds a third
connector contact explicitly assigned to the PHY reference net. Both sources
are exported twice by the digest-pinned KiCad 10.0.0 and 10.0.5 acceptance
lane; normalized netlists and the rule finding must be repeatable.

| Case    | SHA-256                                                            |
| ------- | ------------------------------------------------------------------ |
| fault   | `a6bc8ce5ec66ae7b2b7e9649c26b0ebf20fcda855d9d11f0b6d3e3e3d61cf462` |
| control | `6789b60e42cd430444e62ef98919b7eab5afd402f82e93f24856afad6e6df6e4` |
