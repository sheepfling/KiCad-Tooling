# Synthetic peer bidirectional-pin fixtures

These schematics use two fitted instances of one embedded synthetic
component. Pin 1 is a shared passive signal. Pin 2 is named `DATA_IO` and uses
native electrical type `bidirectional`.

| Fixture             | U1.2        | U2.2        | Expected lint result                                        |
| ------------------- | ----------- | ----------- | ----------------------------------------------------------- |
| `fault.kicad_sch`   | `DATA_IO`   | unassigned  | `component.peer_bidirectional_pin_unconnected` reports U2.2 |
| `control.kicad_sch` | `DATA_IO_A` | `DATA_IO_B` | No peer bidirectional-pin finding                           |

The control keeps the two assignments separate to show that matching
bidirectional pins do not need to share a net. Typed controls also cover a
common-net assignment, DNP peers, all-open peers, different symbols, incomplete
inventories, ambiguous assignments, and other electrical types.

The fixtures are synthetic and are not a project design. Native netlists must
retain exact symbol identity, pin inventory, the `bidirectional` type, and
matching pin-function metadata for the heuristic to apply. The default finding
asks whether the open pin is intentional; it does not establish a required bus
membership, off-board path, or PCB continuity.

SHA-256 source digests:

- `control.kicad_sch`: `1ea8f0a5b92fab8fafd0170adbe6b374f8bc9c24f38b00c00a0ceaafa70e2aa0`
- `fault.kicad_sch`: `5811d43e0298fb4bd8443bf849e8e75665e693561b4981786e768c0c895f4ea3`
