# Generic UART connector review fixtures

These are synthetic tooling regressions. They contain no external board or
project data.

`fault.kicad_sch` places generic connector contacts J1.1/J1.2 on two neutral
net labels assigned to fitted U1 pins whose native functions and electrical
types identify UART TXD/RXD. The heuristic should ask whether the connector
belongs to that serial interface and whether its pinout is documented.
`control.kicad_sch` gives the corresponding connector contacts explicit TXD/RXD
functions; the generic-pin prompt should stay quiet. On the fault, the report
also retains the other connector contacts, their native pin functions, and
their native net assignments. This is review context only: it does not infer
that an extra contact is a return, require that it be connected, or connect it
to board ground.

The digest-pinned KiCad 10.0.0 and 10.0.5 lane exports each source twice, then
compares normalized netlists and lint findings. Source hashes are registered in
`kicad_tooling/ci_hosted_serial_generic_connector_cases.py`.

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `718423c9b69dc7e42233700246ce111731b64c8f63d253e4ca1c4d92d2520dbc` |
| `control.kicad_sch` | `da296b82788c0db25161152488375adab6b06a42c34e73ed332a8452d8084418` |
