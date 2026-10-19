# Synthetic connector footprint-alias fixtures

These tooling-owned schematics exercise a review heuristic for fitted,
PART_ID-free connector symbols that share the same value, footprint, complete
pin inventory, and native pin metadata. Both symbols use generic passive
`Pin_1` and `Pin_2` contacts. Pin 1 is the common assignment anchor.

| Fixture                | J1 pin 2          | J2 pin 2          | Expected result                                                   |
| ---------------------- | ----------------- | ----------------- | ----------------------------------------------------------------- |
| `fault.kicad_sch`      | `SYNTHETIC_NET_2` | `SYNTHETIC_NET_3` | `REVIEW` for `connector.footprint_peer_pin_assignment_divergence` |
| `control.kicad_sch`    | `SYNTHETIC_NET_2` | `SYNTHETIC_NET_2` | No footprint-alias divergence                                     |
| `open-fault.kicad_sch` | `SYNTHETIC_NET_2` | unassigned        | `REVIEW` for `connector.footprint_peer_pin_open_outlier`          |

The open-pin case is also only a review prompt: J1 and J2 have one exact common
anchor on pin 1, and J2 pin 2 is open while J1 pin 2 is assigned. It does not
assert that pin 2 is required or should be connected. Fully open, unanchored,
named-function, and ineligible alias cases are covered by synthetic unit tests.

The matching footprint and value are clues for review, not proof that the
connectors have the same electrical role. The rule does not require common
nets. A project may disable or ignore it with an authored reason, and a
source-matched peer-assignment group can scope the comparison. These fixtures
contain no product project sources or expectations.

SHA-256 source digests:

- `fault.kicad_sch`: `e45b8069603078c1a26198b962b96b20d8a7f9dff39b195b7bb6399e00b323c0`
- `control.kicad_sch`: `d5c77a1b8de808ab82c9f98f0172af7f6f933ce43536dabe00c6fbf83e048e28`
- `open-fault.kicad_sch`: `ba6fd627b7a8e994ca554dbb9f3a1d67197f8a48d5302c5ee6c78318be424605`
