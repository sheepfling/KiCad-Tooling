# Synthetic mixed-open component peer fixtures

These schematics use three fitted instances of one embedded synthetic
component. Both pins have native `passive` types and generic `Pin_1`/`Pin_2`
functions. Pin 1 is an exact `DATA` anchor across all peers. In the fault,
U1.2 and U2.2 share `LOAD` while U3.2 is open. The control assigns all three
target pins to `LOAD`.

| Fixture             | Pin 1 assignments  | Pin 2 assignments        | Expected lint result                                                         |
| ------------------- | ------------------ | ------------------------ | ---------------------------------------------------------------------------- |
| `fault.kicad_sch`   | U1/U2/U3 on `DATA` | U1/U2 on `LOAD`; U3 open | `component.generic_peer_pin_mixed_open` reviews U3.2 when explicitly enabled |
| `control.kicad_sch` | U1/U2/U3 on `DATA` | U1/U2/U3 on `LOAD`       | no mixed-open prompt                                                         |

The rule is default-off. Matching peers, assignment consensus, and the shared
anchor provide comparison context only; they do not establish that Pin 2 must
connect. These fixtures contain no project design or proprietary source and do
not represent a real component requirement.

Source SHA-256:

- `fault.kicad_sch`: `f7dbc6a60581d66e74e5daef25064f5690e0c13a570526974dd5a22044dab430`
- `control.kicad_sch`: `1b079ba2c4af5b4fb40341d3ea7bfb971478327baf80df32026d8cbeea12a8db`
