# Synthetic two-pin varistor regressions

These KiCad schematics are tooling-owned synthetic fixtures. They contain no
product design or customer source. Their minimal embedded symbol declarations
use the standard `Device:Varistor` identity with two pins. The drawing geometry
is illustrative and does not represent a selected part or footprint.

| Fixture                            | Topology                                             | Expected result |
| ---------------------------------- | ---------------------------------------------------- | --------------- |
| `same-net-varistor.kicad_sch`      | Both fitted varistor pins share one local net label. | Review RV1.     |
| `distinct-nets-varistor.kicad_sch` | The pins use separate input/output labels.           | No finding.     |

The review reports a schematic net assignment pattern only. It does not
establish that a protection component is required, correctly rated, correctly
oriented, physically fitted, or connected on the PCB. A same-net varistor may
be intentional and remains a review candidate.

Native exports run twice with digest-pinned KiCad 10.0.0 and 10.0.5. The
normalized netlist and lint result must match across repeated exports. The
fixture lane uses a read-only mount, disabled container networking, and a
separate writable output mount.

Source SHA-256 values:

| Fixture                            | SHA-256                                                            |
| ---------------------------------- | ------------------------------------------------------------------ |
| `same-net-varistor.kicad_sch`      | `c8f563192569de181d597ae31528b4e64782445e69894b9c0c0d37acd7480abf` |
| `distinct-nets-varistor.kicad_sch` | `60369d9cac30ade461b045c99b599b73821fbefc646a7c06f2ce552d31e871a0` |
