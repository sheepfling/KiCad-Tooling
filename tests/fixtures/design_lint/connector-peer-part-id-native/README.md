# Synthetic connector PART_ID peer fixtures

These schematics test generic connector-pin review across two distinct native
symbol IDs that share one synthetic `PART_ID`. Both fitted connectors have the
same value, footprint, complete two-pin inventory, `Pin_1`/`Pin_2` functions,
and passive electrical types.

| Fixture                            | J1 pin 2           | J2 pin 2           | Expected lint result                                    |
| ---------------------------------- | ------------------ | ------------------ | ------------------------------------------------------- |
| `fault.kicad_sch`                  | `SYNTHETIC_RETURN` | Unconnected        | `REVIEW` for `connector.peer_pin_assignment_outlier`    |
| `control.kicad_sch`                | `SYNTHETIC_RETURN` | `SYNTHETIC_RETURN` | No connector peer-pin finding                           |
| `split-assignment-fault.kicad_sch` | `SYNTHETIC_NET_2`  | `SYNTHETIC_NET_3`  | `REVIEW` for `connector.peer_pin_assignment_divergence` |

Pin 1 is assigned to the same synthetic data net in both cases. The fault
demonstrates a missing assignment surfaced by exact part identity and matching
native pin metadata. The control verifies that matching assignments stay
quiet. A matching `PART_ID` is a review clue; it does not say that all copies
must share a net or prove a physical connection. Typed tests also cover
deliberately isolated peer groups, incomplete identity/inventory/metadata,
DNP state, and ambiguous assignments.

The split-assignment fault assigns both generic pin-2 contacts to separate
schematic nets. It exercises the native divergence prompt for the regression
shape where comparable connector returns appear on separately named nets. It
does not assert that those nets must be bonded; a reviewed project contract
must state that requirement.

The source-bound native lane exports both schematics twice with digest-pinned
KiCad 10.0.0 and 10.0.5, then checks the normalized netlist and lint result.
These are tooling-owned fixtures only; no product schematic or project
expectation is included.

SHA-256 source digests:

- `control.kicad_sch`: `b8b85aa1fdc8c62547eab58788b120fa6028a8ba65051126f954432f4dd07d2c`
- `fault.kicad_sch`: `db6f556278611edb21a66f8445f7dfc3a2e456a63783dc3d1e8a79a56a69d478`
- `split-assignment-fault.kicad_sch`:
  `8530bab2ac3537a821be48321e9bb713aa8b2933d714902cc5a30fb4168fa192`
