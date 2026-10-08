# Synthetic peer power-output assignment fixtures

These schematics use two fitted instances of the same embedded synthetic
component. Pin 1 is a shared passive signal. Pin 2 is named `OUT` and uses
native electrical type `power_out`; that function is intentionally not a
recognized named supply alias.

| Fixture             | U1.2     | U2.2       | Expected lint result                                   |
| ------------------- | -------- | ---------- | ------------------------------------------------------ |
| `fault.kicad_sch`   | `VOUT`   | unassigned | `component.peer_power_output_unconnected` reports U2.2 |
| `control.kicad_sch` | `VOUT_A` | `VOUT_B`   | No peer power-output finding                           |

The control keeps both assignments separate to show that matching component
outputs do not need to share a net. Typed controls additionally cover common
assignments, DNP peers, all-open peers, different symbols, incomplete
inventories, ambiguous assignments, named supply/return exclusions, and a
shield-labelled output that remains eligible for review.

The fixture is synthetic and is not a project design. Native netlists must
retain exact symbol identity, pin inventory, and `power_out` type for the
heuristic to apply. The rule asks for review and does not prove that the output
is used or that peer outputs should be common.

SHA-256 source digests:

- `control.kicad_sch`: `1b1d4bb236864087fe619819a3776ad5ef7f4d7d2e462ebb0fc8eaa2c6bf2399`
- `fault.kicad_sch`: `960e1030966e72c7ce197a971cf71418a8274e9e224ae60ef4d3d540af82790b`
