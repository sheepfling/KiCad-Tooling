# Two-pin UART return review fixtures

These are synthetic tooling regressions. They contain no external project or
board data.

`fault.kicad_sch` has a complete two-contact generic connector on native UART
TX/RX nets, with no connector pin declared as a ground or return. The rule
should ask for review without deciding whether the interface needs a local
return. `control.kicad_sch` uses named TXD/RXD connector contacts and must not
receive the generic two-contact prompt.

The digest-pinned native lane exports both schematics twice with KiCad 10.0.0
and 10.0.5. Source digests are pinned in
`kicad_tooling/ci_hosted_serial_connector_return_cases.py`.
