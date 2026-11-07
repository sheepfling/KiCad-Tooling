# USB-C CC unconnected-pin fixtures

These tooling-owned synthetic schematics verify the native netlist evidence
used by the `bus.usb_c_unconnected_cc_pin` review hint. They contain no product
board or project data.

- `fault.kicad_sch` assigns connector J1's CC1 contact, but leaves controller
  U1's CC1 pin unassigned. CC2 remains connected between J1 and U1.
- `control.kicad_sch` connects both CC1 and CC2 between J1 and U1 on separate
  nets.

Reviewed schematic SHA-256 digests:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `ff96866e1820471c9f71f048f4a88bab8000e65126f5ea19a03bfad86d7fe756` |
| `control.kicad_sch` | `294c6944f5613a5364a6d5a5b275f8c81344a1c2d8c8b097b208393b8a7562a9` |

The native lane exports each source twice with digest-pinned KiCad 10.0.0 and
10.0.5 images. It verifies the exact CC pin functions, assignments, explicit
unconnected-pin inventory, repeatable normalized netlists, the expected lint
subject, and zero ERC errors. This validates schematic evidence only; it does
not establish USB-C role, Rp/Rd configuration, VBUS behavior, PCB copper, or
physical continuity.
