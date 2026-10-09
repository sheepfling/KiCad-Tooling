# Synthetic peer power-output assignment fixtures

These schematics use two fitted embedded synthetic symbols with identical
pin numbers, value, and footprint. Both carry the same `PART_ID`. Pin 1 is a
shared passive signal. Pin 2 is labeled with the generic native function
`Pin_2` and uses electrical type `power_out`. This pair verifies that the
native netlist preserves `PART_ID` and identical generic pin metadata, and
that the review can compare equivalent components represented by different
symbol IDs.

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
retain `PART_ID`, complete pin inventories, identical pin-function text, and
`power_out` type for the cross-symbol heuristic to apply. Identical generic
function labels establish only a structural match, not the pin's electrical
role. The rule asks for review and does not prove that the output is used or
that peer outputs should be common.

SHA-256 source digests:

- `control.kicad_sch`: `3b41f81891115ae3e324694f46e41fbe44fb737c86555aa873333aa225b6f34b`
- `fault.kicad_sch`: `76cd57afa2e87980e9914a6508066e7197812bacd68241fe9e29ffd618bb9ff4`
