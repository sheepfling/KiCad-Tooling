# Synthetic peer signal-input fixtures

These schematics use two fitted instances of the same embedded synthetic
component. Pin 1 is a shared passive signal. Pin 2 is named `IN` and uses
native electrical type `input`.

| Fixture             | U1.2     | U2.2       | Expected lint result                                   |
| ------------------- | -------- | ---------- | ------------------------------------------------------ |
| `fault.kicad_sch`   | `INPUT`  | unassigned | `component.peer_signal_input_unconnected` reports U2.2 |
| `control.kicad_sch` | `INPUT_A`| `INPUT_B`  | No peer signal-input finding                           |

The control keeps the two assignments separate to show that matching
component inputs do not need to share a net. Typed controls also cover a
common-net assignment, active-low inputs, DNP peers, all-open peers, different
symbols, incomplete inventories, ambiguous assignments, and other pin types.

The fixture is synthetic and is not a project design. Native netlists must
retain exact symbol identity, pin inventory, and the `input` type for the
heuristic to apply. The default finding asks whether the open input is
intentional; it does not establish the required signal source or prove that
peer inputs should use a common net.

SHA-256 source digests:

- `control.kicad_sch`: `961527991bc45a4545bbf980a7540e81207c0012fa3fbe20772589970b507e15`
- `fault.kicad_sch`: `9d3293d4c7d536549decad392096f118ad0f8cab6e62926572c9784f46f45275`
