# Synthetic connector footprint-alias fixtures

These tooling-owned schematics exercise review heuristics for fitted,
PART_ID-free connector symbols that share the same value, footprint, complete
pin inventory, and native pin metadata. The default cases use generic passive
`Pin_1`/`Pin_2` labels; the numeric cases use native pin-function names `1`/`7`.
Except for the explicitly unanchored case, pin 1 is the common assignment
anchor.

| Fixture                        | Pin function labels | J1 pin 2          | J2 pin 2          | Expected result                                                   |
| ------------------------------ | ------------------- | ----------------- | ----------------- | ----------------------------------------------------------------- |
| `fault.kicad_sch`              | `Pin_1` / `Pin_2`   | `SYNTHETIC_NET_2` | `SYNTHETIC_NET_3` | `REVIEW` for `connector.footprint_peer_pin_assignment_divergence` |
| `control.kicad_sch`            | `Pin_1` / `Pin_2`   | `SYNTHETIC_NET_2` | `SYNTHETIC_NET_2` | No footprint-alias divergence                                     |
| `open-fault.kicad_sch`         | `Pin_1` / `Pin_2`   | `SYNTHETIC_NET_2` | unassigned        | `REVIEW` for `connector.footprint_peer_pin_open_outlier`          |
| `all-open-fault.kicad_sch`     | `Pin_1` / `Pin_2`   | unassigned        | unassigned        | `REVIEW` for `connector.footprint_peer_pin_all_open`              |
| `numeric-fault.kicad_sch`      | `1` / `7`           | `SYNTHETIC_NET_2` | `SYNTHETIC_NET_3` | `REVIEW` for `connector.footprint_peer_pin_assignment_divergence` |
| `numeric-control.kicad_sch`    | `1` / `7`           | `SYNTHETIC_NET_2` | `SYNTHETIC_NET_2` | No footprint-alias divergence                                     |
| `numeric-open-fault.kicad_sch` | `1` / `7`           | `SYNTHETIC_NET_2` | unassigned        | `REVIEW` for `connector.footprint_peer_pin_open_outlier`          |

`unanchored-fault.kicad_sch` assigns both generic pins to different nets on
J1 and J2, leaving no shared-net anchor. It is evaluated only when a current
source-matched connector map explicitly scopes both instances into one
reviewed peer group, and emits a REVIEW prompt for each differing contact.
That scope asks for review; it does not assert that either pair must be joined.

The mixed-open case is a review prompt: J1 and J2 have one exact common anchor
on pin 1, and J2 pin 2 is open while J1 pin 2 is assigned. Neither case asserts
that pin 2 is required or should be connected. The all-open case leaves pin 2
unassigned on both peers while pin 1 remains a common anchor; it is also an
opt-in review prompt and does not assert a connection requirement. Unanchored,
named-function, and ineligible alias cases are covered by synthetic unit tests.
The hosted native lane exports each schematic twice with pinned KiCad 10.0.0
and 10.0.5, then verifies source hashes, normalized-netlist repeatability, and
review outcomes.

Hosted acceptance passed on 2026-10-19 in tag `v0.5.1rc25` (GitHub Actions run
`39297613246`). The tag-selected connector lint gate enabled native fixtures and
exercised the numeric fault/control and open-fault cases on both pinned KiCad
versions. This confirms deterministic schematic-export and lint behavior; it
does not establish that similar connectors have the same electrical role or
require common nets.

The matching footprint and value are clues for review, not proof that the
connectors have the same electrical role. The rule does not require common
nets. A project may disable or ignore it with an authored reason, and a
source-matched peer-assignment group can scope the comparison. These fixtures
contain no product project sources or expectations.

SHA-256 source digests:

- `fault.kicad_sch`: `e45b8069603078c1a26198b962b96b20d8a7f9dff39b195b7bb6399e00b323c0`
- `control.kicad_sch`: `d5c77a1b8de808ab82c9f98f0172af7f6f933ce43536dabe00c6fbf83e048e28`
- `open-fault.kicad_sch`: `ba6fd627b7a8e994ca554dbb9f3a1d67197f8a48d5302c5ee6c78318be424605`
- `all-open-fault.kicad_sch`: `798d07bb64d60bbeab73b7203e052ce557e50b6da6453044ec4ccef686f78c27`
- `numeric-fault.kicad_sch`: `505a7b2d1eaa74c54d476c5cab9cfcc41649ed51a64f2da4ebd9f5beb6a74f94`
- `numeric-control.kicad_sch`: `c8140e9cf9030ccb646121631d186cef97b7d9c76b0d994c2cb3648aaae28a27`
- `numeric-open-fault.kicad_sch`: `1a011151f612ba45769e859e0ada0cf67da46dea50d062e0559e4591f537d270`
- `unanchored-fault.kicad_sch`: `2d8fbf390f3b154d77c0bbc603a7260ddc0ff27cf3b9b2e74ab19242dfc4aa40`
