# Synthetic peer signal-output fixtures

These schematics use two fitted instances of the same embedded synthetic
component. Pin 1 is a shared passive signal. Pin 2 is named `OUT` and uses
native electrical type `output`.

| Fixture             | U1.2     | U2.2       | Expected lint result                                    |
| ------------------- | -------- | ---------- | ------------------------------------------------------- |
| `fault.kicad_sch`   | `VOUT`   | unassigned | `component.peer_signal_output_unconnected` reports U2.2 |
| `control.kicad_sch` | `VOUT_A` | `VOUT_B`   | No peer signal-output finding                           |

The control keeps the two assignments separate to show that matching
component outputs do not need to share a net. Typed controls also cover a
common-net assignment, DNP peers, all-open peers, different symbols,
incomplete inventories, ambiguous assignments, and native `power_out` pins.

The fixture is synthetic and is not a project design. Native netlists must
retain exact symbol identity, pin inventory, and the `output` type for the
heuristic to apply. The rule asks for review; it does not prove that the output
is used or that peer outputs should be common.

SHA-256 source digests:

- `control.kicad_sch`: `bc5d93308322cd66b404bf058afde73b7b538e5590d84160d26b65af2e53f355`
- `fault.kicad_sch`: `0d45eef6e2fc66da65781bb0e06d5c7601788aeb37489e60bf1302bfdad6a04a`
