# Synthetic all-open generic connector peer pins

These tooling-owned schematics test the opt-in
`connector.generic_peer_pin_all_open` review. Two fitted instances of the same
synthetic connector symbol assign pin 1 to the same `+5V` net. Pin 2 is a
generic `Pin_2` passive contact and has no net assignment on either connector
in the fault. The control assigns both pin 2 contacts to `GND`.

The native fixture explicitly enables this default-off rule. It checks that the
native netlist preserves pin identity, function, electrical type, shared
anchor assignment, and the all-open fault/control distinction on the pinned
KiCad 10.0.0 and 10.0.5 images. The warning does not claim that generic pin 2
is a ground or power contact, or that it must be connected. An approved
connector pinout is still needed to decide that.

Cross-symbol peers with a shared `PART_ID` use the same prompt only after
matching value, footprint, complete pin inventory, and per-pin function and
electrical-type metadata are confirmed. The native `PART_ID` fault and shared
assignment control are recorded in the
[connector PART_ID fixture set](../connector-peer-part-id-native/README.md).

| Fixture             | Pin 1             | Pin 2                 | Expected result               |
| ------------------- | ----------------- | --------------------- | ----------------------------- |
| `fault.kicad_sch`   | J1/J2 share `+5V` | J1.2/J2.2 unassigned  | `REVIEW` from the opt-in rule |
| `control.kicad_sch` | J1/J2 share `+5V` | J1.2/J2.2 share `GND` | `PASS`                        |

## Source hashes

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `ef324858a679dd53b4207be2abc9a2d2cf90517af9c86a845c52d4604bcdc9cf` |
| `control.kicad_sch` | `c0cb38abf69437308aba70428c2ef05ae83a51aeb9fab592fe6fef33fb3a0713` |

Receipts stay under the ignored `build/ci/` directory.
